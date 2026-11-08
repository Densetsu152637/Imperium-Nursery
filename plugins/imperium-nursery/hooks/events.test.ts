import { expect, test } from 'claude-code/testing'

import { isCelebration, isReviewer, looksDenied } from './events'

test('celebrations: commits, merged PRs and test runners', () => {
  const yes = [
    'git commit -m "feat: x"',
    'git add . && git commit -m x',
    'git -C repo commit -am y',
    'gh pr merge 12 --squash',
    'pytest -q',
    'python -m pytest tests',
    'python -m unittest discover',
    'npm test',
    'npm run test',
    'pnpm test',
    'yarn test',
    'cargo test --release',
    'go test ./...',
    '"C:\\Users\\x\\claude.exe" plugin test .',
    'claude plugin test .',
  ]
  for (const cmd of yes) expect([cmd, isCelebration(cmd)]).toEqual([cmd, true])
  const no = ['git status', 'git push', 'ls', 'npm install', 'echo hello', 'git commit --dry-run', 'cargo build', 'git log --oneline']
  for (const cmd of no) expect([cmd, isCelebration(cmd)]).toEqual([cmd, false])
})

test('reviewers: by agent type or the brief tag line', () => {
  expect(isReviewer('general-purpose', 'Role: leaf; Profile: critic\nTask ...')).toBe(true)
  expect(isReviewer('general-purpose', 'Role: leaf; Profile: validator')).toBe(true)
  expect(isReviewer('general-purpose', 'Role: leaf; Profile: inspector')).toBe(true)
  expect(isReviewer('general-purpose', 'Role: leaf; Profile: auditor')).toBe(true)
  expect(isReviewer('plugin:critic', 'anything')).toBe(true)
  expect(isReviewer('general-purpose', 'Role: leaf; Profile: implementer')).toBe(false)
  expect(isReviewer('Explore', 'look around')).toBe(false)
})

test('denied permissions are told from ordinary failures by the error wording', () => {
  expect(looksDenied("The user doesn't want to proceed with this tool use.")).toBe(true)
  expect(looksDenied('Permission to use Bash has been denied.')).toBe(true)
  expect(looksDenied('Error: ENOENT no such file')).toBe(false)
  expect(looksDenied(undefined)).toBe(false)
})
