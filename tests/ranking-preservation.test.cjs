'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {verifyPreserved, REVIEW_BRANCH} = require('../research/today-ranking/preservation.cjs');

function git(repo, ...args) { return execFileSync('git', args, {cwd: repo, encoding: 'utf8'}).trim(); }
function fixture(t) {
  const repo = fs.mkdtempSync(path.join(os.tmpdir(), 'ranking-preservation-'));
  t.after(() => fs.rmSync(repo, {recursive: true, force: true}));
  git(repo, 'init', '-q');
  git(repo, 'checkout', '-q', '-b', REVIEW_BRANCH);
  const journal = path.join(repo, 'journal');
  const date = path.join(journal, '2026-10-03');
  fs.mkdirSync(date, {recursive: true});
  const old = path.join(date, '000000000001-old.json.gz');
  const original = Buffer.from([31, 139, 8, 0, 1, 2, 3, 4]);
  fs.writeFileSync(old, original);
  git(repo, 'add', '--', 'journal');
  git(repo, '-c', 'user.name=Offline Test', '-c', 'user.email=offline@example.invalid', 'commit', '-qm', 'baseline observation');
  return {repo, journal, date, old, original};
}

test('preserves HEAD observations and allows new regular-file additions', t => {
  const {repo, journal, date} = fixture(t);
  assert.deepEqual(verifyPreserved(journal), {preservedFiles: 1, addedFiles: 0, bytesChecked: 8});
  assert.deepEqual(verifyPreserved(repo), {preservedFiles: 1, addedFiles: 0, bytesChecked: 8});
  const next = path.join(date, '000000000002-new.json.gz');
  fs.writeFileSync(next, 'new observation');
  assert.equal(verifyPreserved(journal).addedFiles, 1);
  git(repo, 'add', '--', 'journal');
  assert.equal(verifyPreserved(journal).addedFiles, 1);
});

test('detects deleted tail and changed bytes even when Git index is unchanged', t => {
  const {journal, old} = fixture(t);
  fs.unlinkSync(old);
  assert.throws(() => verifyPreserved(journal));
  fs.writeFileSync(old, 'changed observation');
  assert.throws(() => verifyPreserved(journal), /Changed or deleted journal observation/);
});

test('detects staged content after working bytes are restored', t => {
  const {repo, journal, old, original} = fixture(t);
  fs.writeFileSync(old, 'staged replacement');
  git(repo, 'add', '--', 'journal');
  fs.writeFileSync(old, original);
  assert.throws(() => verifyPreserved(journal), /Staged journal change/);
});

test('detects staged mode changes and symlink additions', t => {
  const {repo, journal, date, old} = fixture(t);
  git(repo, 'update-index', '--chmod=+x', '--', path.relative(repo, old));
  assert.throws(() => verifyPreserved(journal), /Staged journal change/);
  git(repo, 'update-index', '--chmod=-x', '--', path.relative(repo, old));
  const linkBlob = execFileSync('git', ['hash-object', '-w', '--stdin'], {cwd: repo, input: 'target', encoding: 'utf8'}).trim();
  const linkPath = path.relative(repo, path.join(date, 'link.json.gz')).replaceAll(path.sep, '/');
  git(repo, 'update-index', '--add', '--cacheinfo', `120000,${linkBlob},${linkPath}`);
  assert.throws(() => verifyPreserved(journal), /Unsafe staged journal addition/);
});

test('requires the dedicated review branch', t => {
  const {repo, journal} = fixture(t);
  git(repo, 'checkout', '-q', '-b', 'codex/wrong-review');
  assert.throws(() => verifyPreserved(journal), /Wrong journal review branch/);
});
