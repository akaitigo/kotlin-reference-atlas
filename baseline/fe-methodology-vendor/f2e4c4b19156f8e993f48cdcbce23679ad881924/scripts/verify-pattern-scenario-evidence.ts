import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import registry from "../packages/registry/generated/registry.json" with { type: "json" };

const root = process.cwd();
const digest = (value: Buffer | string) => `sha256:${createHash("sha256").update(value).digest("hex")}`;
const filesDigest = async (files: string[]) => {
  const hash = createHash("sha256");
  for (const file of files) hash.update(file).update("\0").update(await readFile(path.join(root, file))).update("\0");
  return `sha256:${hash.digest("hex")}`;
};
const assert = (condition: unknown, message: string): asserts condition => { if (!condition) throw new Error(message); };
type TestRecord = {
  pattern_id: string; variant_id: string; scenario: string; source_digest: string; outcome: string; attempts: number; final_status: string; error: string | null;
  oracle: { driven_actions: { repeated_start: number; disconnect: number; recover: number }; observed_queue_depths: number[]; maximum_queue_depth: number; final_state: { pattern: string; strategy: string; phase: string; connected: boolean; sequence: number; queued: number } };
  trace: { path: string; digest: string; bytes: number; action_stream: boolean; network_stream: boolean; resource_stream: boolean };
  screenshot: { path: string; digest: string; bytes: number };
};
const report = JSON.parse(await readFile(path.join(root, "artifacts/pattern-scenarios/results.json"), "utf8")) as {
  status: string; command: string; profile: string; counts: { rows: number; variants: number; total: number; passed: number; failed: number; flaky: number; skipped: number };
  source_digest: string; harness_digest: string;
  environment: { node: string; platform: string; architecture: string; playwright: string; browser_name: string; browser_version: string; browser_channel: string; workers: number; retries: number; viewport: { width: number; height: number; device_scale_factor: number }; trace_mode: string };
  tests: TestRecord[];
};
const expectedPatterns = ["reactive/background-sync-status", "reactive/network-offline-recovery"];
const expectedKeys = expectedPatterns.flatMap((patternId) => {
  const pattern = registry.patterns.find((candidate) => candidate.id === patternId);
  if (!pattern) throw new Error(`Expected Pattern is missing: ${patternId}`);
  return pattern.variants.map((variant) => `${patternId}\0boundary\0${variant.id}`);
}).sort();
const actualKeys = report.tests.map((test) => `${test.pattern_id}\0${test.scenario}\0${test.variant_id}`).sort();
assert(JSON.stringify(actualKeys) === JSON.stringify(expectedKeys), "Dedicated Scenario report does not contain the exact first-tranche Pattern/Variant rows.");
assert(report.status === "passed" && report.command === "pnpm pattern-scenario:test" && report.profile === "local-real-browser", "Dedicated Scenario run identity is invalid.");
assert(report.counts.rows === 2 && report.counts.variants === 4 && report.counts.total === 4 && report.counts.passed === 4 && report.counts.failed === 0 && report.counts.flaky === 0 && report.counts.skipped === 0, "Dedicated Scenario counts must remain 2 rows / 4 first-attempt passes.");
assert(report.environment.browser_name === "chromium" && /^\d+\.\d+\.\d+(?:\.\d+)?$/.test(report.environment.browser_version) && report.environment.workers === 1 && report.environment.retries === 0 && report.environment.trace_mode === "on", "Dedicated Scenario Browser identity or execution profile is invalid.");
const sourceFiles = ["experiments/_shared/reactive-lab.ts", ...report.tests.map((test) => `experiments/${test.pattern_id}/variants/${test.variant_id}/entry.ts`)];
assert(report.source_digest === await filesDigest([...new Set(sourceFiles)]), "Dedicated Scenario source digest is stale.");
const harnessFiles = ["pattern-scenario-e2e/reactive-queue-boundary.spec.ts", "playwright.pattern-scenario.config.ts", "scripts/reporters/pattern-scenario-evidence-reporter.ts", "scripts/verify-pattern-scenario-evidence.ts"];
assert(report.harness_digest === await filesDigest(harnessFiles), "Dedicated Scenario harness digest is stale.");
for (const test of report.tests) {
  const pattern = registry.patterns.find((candidate) => candidate.id === test.pattern_id)!;
  assert(test.source_digest === `sha256:${registry.artifacts.sourceHashes[`${test.pattern_id}::${test.variant_id}`]}`, `Variant source binding drift: ${test.pattern_id} / ${test.variant_id}`);
  assert(pattern.variants.some((variant) => variant.id === test.variant_id), `Unknown Variant record: ${test.pattern_id} / ${test.variant_id}`);
  assert(test.scenario === "boundary" && test.outcome === "expected" && test.attempts === 1 && test.final_status === "passed" && test.error === null, `Dedicated Scenario attempt failed or retried: ${test.pattern_id} / ${test.variant_id}`);
  assert(test.oracle.driven_actions.repeated_start === 8 && test.oracle.driven_actions.disconnect === 1 && test.oracle.driven_actions.recover === 1, `Dedicated Scenario did not drive the declared action sequence: ${test.pattern_id} / ${test.variant_id}`);
  assert(test.oracle.observed_queue_depths.length === 10 && Math.max(...test.oracle.observed_queue_depths) === 1 && test.oracle.maximum_queue_depth === 1, `Queue boundary Oracle failed: ${test.pattern_id} / ${test.variant_id}`);
  assert(test.oracle.final_state.pattern === test.pattern_id.split("/").at(-1) && test.oracle.final_state.strategy === test.variant_id && test.oracle.final_state.phase === "recovered" && test.oracle.final_state.connected && test.oracle.final_state.sequence === 9 && test.oracle.final_state.queued === 0, `Final recovery state drift: ${test.pattern_id} / ${test.variant_id}`);
  for (const artifact of [test.trace, test.screenshot]) {
    const bytes = await readFile(path.join(root, artifact.path));
    assert(bytes.byteLength === artifact.bytes && digest(bytes) === artifact.digest, `Dedicated Scenario Artifact digest drift: ${artifact.path}`);
  }
  assert(test.trace.action_stream && test.trace.network_stream && test.trace.resource_stream, `Dedicated Scenario Trace streams are incomplete: ${test.pattern_id} / ${test.variant_id}`);
}
console.log(`Verified dedicated Pattern Scenario Evidence: ${report.counts.rows} rows / ${report.counts.variants} Variant traces on chromium ${report.environment.browser_version}.`);
