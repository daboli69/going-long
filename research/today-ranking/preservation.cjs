'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {execFileSync} = require('node:child_process');

const REVIEW_BRANCH = 'codex/going-long-daily-review';
function git(cwd, ...args) {
  return execFileSync('git', args, {cwd, encoding: 'buffer', maxBuffer: 256 * 1024 * 1024});
}
function output(cwd, ...args) { return git(cwd, ...args).toString('utf8').trim(); }
function within(base, target) {
  const relative = path.relative(base, target);
  return relative === '' || (!path.isAbsolute(relative) && relative !== '..' && !relative.startsWith('..' + path.sep));
}
function safeFile(root, repo, gitPath) {
  if (!gitPath || gitPath.includes('\\') || path.posix.isAbsolute(gitPath) || gitPath.split('/').some(part => !part || part === '.' || part === '..')) throw new Error('Unsafe journal Git path');
  const target = path.resolve(repo, ...gitPath.split('/'));
  if (!within(root, target)) throw new Error('Tracked path escapes journal root');
  let current = repo;
  for (const part of gitPath.split('/')) {
    current = path.join(current, part);
    const stat = fs.lstatSync(current);
    if (stat.isSymbolicLink()) throw new Error('Journal symlink is forbidden: ' + gitPath);
    if (current !== target && !stat.isDirectory()) throw new Error('Journal path component is not a directory: ' + gitPath);
    if (current === target && !stat.isFile()) throw new Error('Journal observation is not a regular file: ' + gitPath);
  }
  return target;
}
function parseEntries(buffer, kind) {
  const entries = new Map();
  for (const line of buffer.subarray(0, buffer.length - (buffer.at(-1) === 0 ? 1 : 0)).toString('binary').split('\0')) {
    if (!line) continue;
    const tab = line.indexOf('\t');
    if (tab < 0) throw new Error('Malformed Git ' + kind + ' entry');
    const bytes = Buffer.from(line.slice(tab + 1), 'binary');
    const name = bytes.toString('utf8');
    if (!Buffer.from(name, 'utf8').equals(bytes)) throw new Error('Non-UTF-8 journal path is unsafe');
    const header = line.slice(0, tab);
    const match = kind === 'HEAD' ? /^(\d{6}) blob ([0-9a-f]+)$/.exec(header) : /^(\d{6}) ([0-9a-f]+) ([0-3])$/.exec(header);
    if (!match || entries.has(name)) throw new Error('Malformed or duplicate Git ' + kind + ' entry');
    entries.set(name, {mode: match[1], hash: match[2], stage: kind === 'index' ? Number(match[3]) : 0});
  }
  return entries;
}
function scanFiles(root, skipGit) {
  let count = 0;
  function visit(directory, top) {
    for (const entry of fs.readdirSync(directory, {withFileTypes: true})) {
      if (top && skipGit && entry.name === '.git') continue;
      const target = path.join(directory, entry.name);
      const stat = fs.lstatSync(target);
      if (stat.isSymbolicLink()) throw new Error('Journal symlink is forbidden: ' + target);
      if (stat.isDirectory()) visit(target, false);
      else if (stat.isFile()) count++;
      else throw new Error('Unsafe journal file type: ' + target);
    }
  }
  visit(root, true);
  return count;
}

function verifyPreserved(journalRoot) {
  if (typeof journalRoot !== 'string' || !journalRoot) throw new TypeError('Journal root path required');
  const root = path.resolve(journalRoot);
  if (!fs.existsSync(root) || !fs.lstatSync(root).isDirectory() || fs.lstatSync(root).isSymbolicLink()) throw new Error('Journal root must be a real directory');
  const repo = path.resolve(output(root, 'rev-parse', '--show-toplevel'));
  if (!within(repo, root)) throw new Error('Journal root must be inside its Git repository');
  if (output(repo, 'symbolic-ref', '--quiet', '--short', 'HEAD') !== REVIEW_BRANCH) throw new Error('Wrong journal review branch');
  const format = output(repo, 'rev-parse', '--show-object-format');
  if (format !== 'sha1' && format !== 'sha256') throw new Error('Unsupported Git object format');
  const relative = path.relative(repo, root).split(path.sep).join('/');
  const pathspec = relative || '.';
  const head = parseEntries(git(repo, 'ls-tree', '-r', '-z', 'HEAD', '--', pathspec), 'HEAD');
  const index = parseEntries(git(repo, 'ls-files', '--stage', '-z', '--', pathspec), 'index');
  let bytesChecked = 0;
  for (const [name, expected] of head) {
    if (expected.mode !== '100644' && expected.mode !== '100755') throw new Error('Unsafe tracked journal mode: ' + name);
    const staged = index.get(name);
    if (!staged || staged.stage !== 0 || staged.mode !== expected.mode || staged.hash !== expected.hash) throw new Error('Staged journal change or deletion: ' + name);
    const file = safeFile(root, repo, name);
    const bytes = fs.readFileSync(file);
    const actual = crypto.createHash(format).update(`blob ${bytes.length}\0`).update(bytes).digest('hex');
    if (actual !== expected.hash) throw new Error('Changed or deleted journal observation: ' + name);
    if (process.platform !== 'win32') {
      const executable = Boolean(fs.statSync(file).mode & 0o111);
      if (executable !== (expected.mode === '100755')) throw new Error('Changed journal file mode: ' + name);
    }
    bytesChecked += bytes.length;
  }
  for (const [name, staged] of index) {
    if (head.has(name)) continue;
    if (staged.stage !== 0 || (staged.mode !== '100644' && staged.mode !== '100755')) throw new Error('Unsafe staged journal addition: ' + name);
  }
  const totalFiles = scanFiles(root, root === repo);
  return {preservedFiles: head.size, addedFiles: totalFiles - head.size, bytesChecked};
}

module.exports = {verifyPreserved, REVIEW_BRANCH};
