// Pure classifiers the event hooks use. No `$`.

const GIT_COMMIT = /(?:^|[\s;&|(])git(?:\s+(?:-[cC]\s+\S+|--[a-z-]+(?:=\S+)?))*\s+commit\b(?!.*--dry-run)/
const GH_MERGE = /(?:^|[\s;&|(])gh\s+pr\s+merge\b/
const TEST_RUNNERS: RegExp[] = [
  /(?:^|[\s;&|("'\/])(?:pytest|py\.test)\b/,
  /\bpython3?(?:\.exe)?\s+-m\s+(?:pytest|unittest)\b/,
  /(?:^|[\s;&|(])(?:npm|pnpm|yarn)\s+(?:run\s+)?test\b/,
  /(?:^|[\s;&|(])cargo\s+test\b/,
  /(?:^|[\s;&|(])go\s+test\b/,
  /\bclaude(?:\.exe)?["']?\s+plugin\s+test\b/,
]

/** A command whose success is worth a party: a commit, a merged PR, a passing test run. */
export function isCelebration(command: string): boolean {
  return GIT_COMMIT.test(command) || GH_MERGE.test(command) || TEST_RUNNERS.some(r => r.test(command))
}

/** Profiles whose work is reviewing finished output. */
export const REVIEW_PROFILES = ['critic', 'validator', 'inspector', 'auditor']

// The brief's tag line, e.g. `Role: leaf; Profile: critic`: the first match counts.
const PROFILE_TAG = /\bProfile:\s*([a-z-]+)/i

/** True when a subagent is a reviewer: its type or the brief's `Profile:` tag names one. */
export function isReviewer(subagentType: string, prompt: string): boolean {
  const bare = subagentType.replace(/^[^:]*:/, '').trim().toLowerCase()
  if (REVIEW_PROFILES.includes(bare)) return true
  const tag = PROFILE_TAG.exec(prompt)?.[1]?.toLowerCase() ?? ''
  return REVIEW_PROFILES.includes(tag)
}

// What a refused permission reads like as the model receives it. Heuristic: the engine's
// wording is not part of the API, so a miss is shown as `failed` instead of `confused`.
const DENIED =
  /doesn'?t want to proceed|rejected the tool use|tool use was rejected|permission to use .{0,80} (?:has been )?denied|denied by (?:the )?(?:user|permission|hook)|was denied by|user (?:rejected|declined|denied)/i

/** Whether a tool error's text says the person (or a rule) refused the call. */
export const looksDenied = (text: string | undefined): boolean => DENIED.test(text ?? '')
