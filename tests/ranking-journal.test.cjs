'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const zlib = require('node:zlib');
const {spawn} = require('node:child_process');
const journal = require('../shared/ranking-journal.cjs');

function fixture(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'ranking-journal-'));
  t.after(() => fs.rmSync(root, {recursive: true, force: true}));
  return root;
}
const at = '2026-10-02T14:30:00-04:00';
const input = (key = 'candidate:1', payload = {b: 2, a: 1}) => ({kind: 'snapshot', key, observedAt: at, payload});
const files = root => fs.readdirSync(root).filter(name => name.endsWith('.json.gz'));

test('canonical JSON and payload hashes are order independent and reject non-JSON values', () => {
  assert.equal(journal.canonicalJSON({b: [1, {z: true, a: null}], a: -0}), '{"a":0,"b":[1,{"a":null,"z":true}]}');
  assert.equal(journal.hashPayload({b: 2, a: 1}), journal.hashPayload({a: 1, b: 2}));
  for (const value of [NaN, Infinity, -Infinity, undefined, {x: undefined}, [1, , 3], new Date(), {x: BigInt(1)}]) {
    assert.throws(() => journal.canonicalJSON(value));
  }
  const cyclic = {}; cyclic.self = cyclic;
  assert.throws(() => journal.canonicalJSON(cyclic), /cycles/);
});

test('append is immutable by logical key, idempotent for identical content, and chained', t => {
  const root = fixture(t);
  const first = journal.appendRecord(root, input());
  assert.equal(first.seq, 1);
  assert.equal(first.prevHash, null);
  assert.equal(journal.appendRecord(root, input('candidate:1', {a: 1, b: 2})).hash, first.hash);
  assert.equal(files(root).length, 1);
  assert.throws(() => journal.appendRecord(root, input('candidate:1', {a: 3})), /Conflicting journal key/);
  const second = journal.appendRecord(root, {kind: 'settlement', key: 'settlement:1', observedAt: at, payload: {outcome: 'win'}});
  assert.equal(second.prevHash, first.hash);
  assert.deepEqual(journal.readRecords(root), [first, second]);
  assert.deepEqual(journal.findRecord(root, 'candidate:1'), first);
  assert.equal(journal.findRecord(root, 'missing'), null);
});

test('invalidation appends a new record and preserves the original snapshot', t => {
  const root = fixture(t);
  const first = journal.appendRecord(root, input());
  const invalidation = journal.appendRecord(root, {kind: 'invalidation', key: 'invalidation:1', observedAt: at, payload: {targetHash: first.hash, reason: 'late correction'}});
  assert.equal(invalidation.prevHash, first.hash);
  assert.deepEqual(journal.readRecords(root).map(record => record.kind), ['snapshot', 'invalidation']);
  assert.deepEqual(journal.findRecord(root, first.key), first);
});

test('invalid timestamps, types, and excessive payloads never publish', t => {
  const root = fixture(t);
  for (const observedAt of ['2026-02-30T00:00:00Z', '2026-10-02T14:30:00', '2026-13-01T00:00:00Z', '2026-10-02T25:00:00Z']) {
    assert.throws(() => journal.appendRecord(root, {...input(), observedAt}));
  }
  assert.throws(() => journal.appendRecord(root, {...input(), kind: 'other'}));
  assert.throws(() => journal.appendRecord(root, {...input(), payload: {x: Infinity}}));
  assert.throws(() => journal.appendRecord(root, input('', {})));
  assert.throws(() => journal.appendRecord(root, input('large', {x: 'x'.repeat(journal.LIMITS.maxRecordBytes)})), /limit/);
  assert.equal(journal.readRecords(root).length, 0);
});

test('tampering with canonical content or truncating gzip fails closed', t => {
  const root = fixture(t);
  journal.appendRecord(root, input());
  const file = path.join(root, files(root)[0]);
  const original = fs.readFileSync(file);
  const changed = JSON.parse(zlib.gunzipSync(original).toString('utf8'));
  changed.payload.a = 99;
  fs.writeFileSync(file, zlib.gzipSync(JSON.stringify(changed)));
  assert.throws(() => journal.readRecords(root), /hash/);
  assert.throws(() => journal.appendRecord(root, input('another')), /hash/);
  assert.equal(fs.existsSync(path.join(root, '.lock')), false);
  fs.writeFileSync(file, original.subarray(0, 9));
  assert.throws(() => journal.readRecords(root), /decompression/);
});

test('sequence gaps, pending writes, unknown entries, and locks fail closed', t => {
  const root = fixture(t);
  journal.appendRecord(root, input());
  const filename = files(root)[0];
  fs.renameSync(path.join(root, filename), path.join(root, `000000000002${filename.slice(12)}`));
  assert.throws(() => journal.readRecords(root), /gap/);
  fs.renameSync(path.join(root, `000000000002${filename.slice(12)}`), path.join(root, filename));
  fs.writeFileSync(path.join(root, '.pending-abandoned'), 'partial');
  assert.throws(() => journal.readRecords(root), /Unexpected journal entry/);
  assert.throws(() => journal.appendRecord(root, input('next')), /Unexpected journal entry/);
  fs.unlinkSync(path.join(root, '.pending-abandoned'));
  fs.writeFileSync(path.join(root, 'notes.txt'), 'unexpected');
  assert.throws(() => journal.readRecords(root), /Unexpected journal entry/);
  fs.unlinkSync(path.join(root, 'notes.txt'));
  fs.mkdirSync(path.join(root, '.lock'));
  assert.throws(() => journal.readRecords(root), /locked/);
  assert.throws(() => journal.appendRecord(root, input('next')), /EEXIST/);
  assert.equal(fs.existsSync(path.join(root, '.lock')), true);
});

function worker(root, payload) {
  const modulePath = path.resolve(__dirname, '../shared/ranking-journal.cjs');
  const script = `const j=require(process.argv[1]);try{j.appendRecord(process.argv[2],{kind:'snapshot',key:'race',observedAt:'${at}',payload:{n:Number(process.argv[3])}});process.exit(0)}catch(e){process.stderr.write(e.message);process.exit(2)}`;
  return new Promise(resolve => {
    const child = spawn(process.execPath, ['-e', script, modulePath, root, String(payload)], {stdio: ['ignore', 'ignore', 'pipe']});
    let error = '';
    child.stderr.on('data', chunk => { error += chunk; });
    child.on('close', code => resolve({code, error}));
  });
}

test('competing worker processes cannot replace or double publish a logical key', async t => {
  const root = fixture(t);
  const results = await Promise.all([worker(root, 1), worker(root, 2)]);
  assert.equal(results.filter(result => result.code === 0).length, 1, JSON.stringify(results));
  assert.match(results.find(result => result.code !== 0).error, /EEXIST|Conflicting journal key/);
  assert.equal(journal.readRecords(root).length, 1);
  assert.equal(files(root).length, 1);
});
