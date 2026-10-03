'use strict';

// Prospective research journal. The root is a dedicated directory; do not put
// unrelated files there. Limits bound synchronous scans and gzip expansion.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const zlib = require('node:zlib');

const LIMITS = Object.freeze({
  maxRecordBytes: 1024 * 1024,
  maxCompressedBytes: 2 * 1024 * 1024,
  maxRecords: 50000,
  maxTotalCompressedBytes: 256 * 1024 * 1024,
  maxTotalRecordBytes: 256 * 1024 * 1024,
  maxKeyBytes: 1024,
});
const KINDS = new Set(['snapshot', 'settlement', 'invalidation', 'status']);
const FILE_RE = /^(\d{12})-([0-9a-f]{64})\.json\.gz$/;
const SHA_RE = /^[0-9a-f]{64}$/;
const LOCK = '.lock';

function canonicalJSON(value) {
  const active = new Set();
  function encode(item) {
    if (item === null || typeof item === 'boolean' || typeof item === 'string') return JSON.stringify(item);
    if (typeof item === 'number') {
      if (!Number.isFinite(item)) throw new TypeError('Journal JSON numbers must be finite');
      return JSON.stringify(item);
    }
    if (typeof item !== 'object') throw new TypeError('Journal values must be JSON');
    if (active.has(item)) throw new TypeError('Journal JSON cannot contain cycles');
    const proto = Object.getPrototypeOf(item);
    if (Array.isArray(item)) {
      if (Object.getOwnPropertySymbols(item).length) throw new TypeError('Journal JSON cannot contain symbol keys');
      active.add(item);
      try {
        const parts = [];
        for (let i = 0; i < item.length; i++) {
          if (!Object.hasOwn(item, i)) throw new TypeError('Journal JSON cannot contain sparse arrays');
          const descriptor = Object.getOwnPropertyDescriptor(item, String(i));
          if (!descriptor || !Object.hasOwn(descriptor, 'value')) throw new TypeError('Journal JSON cannot contain accessors');
          parts.push(encode(descriptor.value));
        }
        const own = Object.keys(item);
        if (own.some(key => key !== 'length' && !/^(0|[1-9]\d*)$/.test(key))) throw new TypeError('Journal arrays cannot contain extra properties');
        return `[${parts.join(',')}]`;
      } finally { active.delete(item); }
    }
    if (proto !== Object.prototype && proto !== null) throw new TypeError('Journal values must be plain JSON objects');
    if (Object.getOwnPropertySymbols(item).length) throw new TypeError('Journal JSON cannot contain symbol keys');
    active.add(item);
    try {
      return `{${Object.keys(item).sort().map(key => {
        const descriptor = Object.getOwnPropertyDescriptor(item, key);
        if (!descriptor || !Object.hasOwn(descriptor, 'value')) throw new TypeError('Journal JSON cannot contain accessors');
        return `${JSON.stringify(key)}:${encode(descriptor.value)}`;
      }).join(',')}}`;
    } finally { active.delete(item); }
  }
  return encode(value);
}

function hashPayload(value) {
  return crypto.createHash('sha256').update(canonicalJSON(value), 'utf8').digest('hex');
}

function validObservedAt(value) {
  if (typeof value !== 'string') return false;
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!match) return false;
  const [, y, mo, d, h, mi, s, zone] = match;
  const year = Number(y), month = Number(mo), day = Number(d);
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (month < 1 || month > 12 || day < 1 || day > days[month - 1] || Number(h) > 23 || Number(mi) > 59 || Number(s) > 59) return false;
  if (zone !== 'Z' && (Number(zone.slice(1, 3)) > 23 || Number(zone.slice(4)) > 59)) return false;
  return Number.isFinite(Date.parse(value));
}

function validateInput(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) throw new TypeError('Journal record must be an object');
  const {kind, key, observedAt, payload} = input;
  if (!KINDS.has(kind)) throw new TypeError('Invalid journal kind');
  if (typeof key !== 'string' || !key || Buffer.byteLength(key, 'utf8') > LIMITS.maxKeyBytes) throw new TypeError('Invalid journal key');
  if (!validObservedAt(observedAt)) throw new TypeError('observedAt must be a valid ISO timestamp with timezone');
  const payloadJSON = canonicalJSON(payload);
  if (Buffer.byteLength(payloadJSON, 'utf8') > LIMITS.maxRecordBytes) throw new RangeError('Journal payload exceeds record limit');
  return {kind, key, observedAt, payload};
}

function checkedRoot(root) {
  if (typeof root !== 'string' || !root) throw new TypeError('Journal root must be a directory path');
  return path.resolve(root);
}

function inspect(root, ownLock = false) {
  if (!fs.existsSync(root)) return [];
  if (!fs.statSync(root).isDirectory()) throw new Error('Journal root is not a directory');
  const entries = fs.readdirSync(root, {withFileTypes: true});
  const files = [];
  let total = 0;
  for (const entry of entries) {
    if (entry.name === LOCK && ownLock && entry.isDirectory()) continue;
    if (entry.name === LOCK) throw new Error('Journal is locked');
    const match = FILE_RE.exec(entry.name);
    if (!match || !entry.isFile()) throw new Error(`Unexpected journal entry: ${entry.name}`);
    const stat = fs.lstatSync(path.join(root, entry.name));
    if (!stat.isFile() || stat.size > LIMITS.maxCompressedBytes) throw new Error(`Invalid journal file: ${entry.name}`);
    total += stat.size;
    if (total > LIMITS.maxTotalCompressedBytes) throw new RangeError('Journal total size limit exceeded');
    files.push({name: entry.name, seq: Number(match[1]), hash: match[2]});
  }
  if (files.length > LIMITS.maxRecords) throw new RangeError('Journal record count limit exceeded');
  files.sort((a, b) => a.seq - b.seq);
  const records = [];
  const keys = new Set();
  let previousHash = null;
  let totalRaw = 0;
  for (const file of files) {
    const expectedSeq = records.length + 1;
    if (file.seq !== expectedSeq) throw new Error(`Journal sequence gap or duplicate at ${file.name}`);
    const compressed = fs.readFileSync(path.join(root, file.name));
    if (compressed.length > LIMITS.maxCompressedBytes) throw new Error(`Journal file grew while reading: ${file.name}`);
    let raw;
    try { raw = zlib.gunzipSync(compressed, {maxOutputLength: LIMITS.maxRecordBytes}); }
    catch (error) { throw new Error(`Journal decompression failed: ${file.name}`, {cause: error}); }
    totalRaw += raw.length;
    if (totalRaw > LIMITS.maxTotalRecordBytes) throw new RangeError('Journal total record size limit exceeded');
    let record;
    try { record = JSON.parse(raw.toString('utf8')); }
    catch (error) { throw new Error(`Journal JSON is invalid: ${file.name}`, {cause: error}); }
    if (!record || Array.isArray(record) || typeof record !== 'object' || Object.keys(record).sort().join(',') !== 'hash,key,kind,observedAt,payload,prevHash,seq') throw new Error(`Journal record shape is invalid: ${file.name}`);
    validateInput(record);
    if (record.seq !== expectedSeq || record.prevHash !== previousHash || !SHA_RE.test(record.hash)) throw new Error(`Journal chain is invalid: ${file.name}`);
    const {hash, ...content} = record;
    const computed = hashPayload(content);
    if (hash !== computed || file.hash !== hash) throw new Error(`Journal hash is invalid: ${file.name}`);
    if (raw.toString('utf8') !== canonicalJSON(record)) throw new Error(`Journal bytes are not canonical: ${file.name}`);
    if (keys.has(record.key)) throw new Error(`Duplicate journal key: ${record.key}`);
    keys.add(record.key);
    records.push(record);
    previousHash = hash;
  }
  return records;
}

function readRecords(root) { return inspect(checkedRoot(root)); }
function findRecord(root, key) { return readRecords(root).find(record => record.key === key) ?? null; }

function appendRecord(root, input) {
  const directory = checkedRoot(root);
  const candidate = validateInput(input);
  fs.mkdirSync(directory, {recursive: true});
  const lockPath = path.join(directory, LOCK);
  fs.mkdirSync(lockPath); // Exclusive; a stale lock requires explicit human inspection.
  try {
    const records = inspect(directory, true);
    const existing = records.find(record => record.key === candidate.key);
    if (existing) {
      if (existing.kind === candidate.kind && existing.observedAt === candidate.observedAt && canonicalJSON(existing.payload) === canonicalJSON(candidate.payload)) return existing;
      throw new Error(`Conflicting journal key: ${candidate.key}`);
    }
    if (records.length >= LIMITS.maxRecords) throw new RangeError('Journal record count limit exceeded');
    const seq = records.length + 1;
    const content = {seq, prevHash: records.at(-1)?.hash ?? null, ...candidate};
    const hash = hashPayload(content);
    const record = {...content, hash};
    const raw = Buffer.from(canonicalJSON(record), 'utf8');
    if (raw.length > LIMITS.maxRecordBytes) throw new RangeError('Journal record exceeds record limit');
    const priorRawBytes = records.reduce((sum, prior) => sum + Buffer.byteLength(canonicalJSON(prior), 'utf8'), 0);
    if (priorRawBytes + raw.length > LIMITS.maxTotalRecordBytes) throw new RangeError('Journal total record size limit exceeded');
    const compressed = zlib.gzipSync(raw, {mtime: 0});
    if (compressed.length > LIMITS.maxCompressedBytes) throw new RangeError('Compressed journal record exceeds limit');
    const usedBytes = records.reduce((sum, prior) => {
      const priorName = `${String(prior.seq).padStart(12, '0')}-${prior.hash}.json.gz`;
      return sum + fs.statSync(path.join(directory, priorName)).size;
    }, 0);
    if (usedBytes + compressed.length > LIMITS.maxTotalCompressedBytes) throw new RangeError('Journal total size limit exceeded');
    const name = `${String(seq).padStart(12, '0')}-${hash}.json.gz`;
    const pending = path.join(directory, `.pending-${process.pid}-${crypto.randomUUID()}`);
    const fd = fs.openSync(pending, 'wx');
    try { fs.writeFileSync(fd, compressed); fs.fsyncSync(fd); }
    finally { fs.closeSync(fd); }
    // A hard link publishes atomically and fails if the final name exists.
    // Deliberately preserve any pending file on failure for manual inspection.
    fs.linkSync(pending, path.join(directory, name));
    fs.unlinkSync(pending);
    return record;
  } finally {
    // Release only our still-empty lock directory; never remove foreign data.
    fs.rmdirSync(lockPath);
  }
}

module.exports = {appendRecord, readRecords, findRecord, canonicalJSON, hashPayload, LIMITS};
