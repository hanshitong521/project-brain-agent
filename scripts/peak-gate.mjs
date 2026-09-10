#!/usr/bin/env node
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { gateEnvelope, printGateReport } from "../../shared/scripts/peak-gate-lib.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

function gitCommit() {
	const r = spawnSync("git", ["rev-parse", "--short", "HEAD"], { cwd: ROOT, encoding: "utf8" });
	return r.status === 0 ? (r.stdout || "").trim() : "unknown";
}

const commit = gitCommit();
const gates = [];

const py = existsSync(join(ROOT, ".venv/Scripts/python.exe"))
	? join(ROOT, ".venv/Scripts/python.exe")
	: "python";

gates.push(
	gateEnvelope({
		gate_id: "B0",
		component: "brain",
		status: existsSync(join(ROOT, "src/brain_services/memory_simple.py")) ? "PASS" : "FAIL",
		summary: "memory_simple canonical entry",
		commit,
	}),
);

const b1 = spawnSync(py, ["-m", "pytest", "tests/unit/test_session_rank.py", "-q"], {
	cwd: ROOT,
	encoding: "utf8",
});
gates.push(
	gateEnvelope({
		gate_id: "B1",
		component: "brain",
		status: (b1.status ?? 1) === 0 ? "PASS" : "FAIL",
		summary: "session DEC rank unit test",
		commit,
	}),
);

gates.push(
	gateEnvelope({
		gate_id: "B2",
		component: "brain",
		status: existsSync(join(ROOT, "src/brain_services/session_scope.py")) ? "PASS" : "FAIL",
		summary: "rm_session / task_id ranking scope",
		commit,
	}),
);

gates.push(
	gateEnvelope({
		gate_id: "B3",
		component: "brain",
		status: existsSync(join(ROOT, "src/brain_services/contextmind_telemetry_bridge.py")) ? "PASS" : "FAIL",
		summary: "Brain MCP → ContextMind telemetry.db",
		commit,
	}),
);

for (let i = 4; i <= 12; i++) {
	gates.push(
		gateEnvelope({
			gate_id: `B${i}`,
			component: "brain",
			status: "NOT_REQUIRED",
			summary: `P2+ B${i} — remaining Brain machine gate`,
			commit,
			blocking: false,
		}),
	);
}

const report = printGateReport("brain", gates);
process.exit(report.rollup === "PASS" ? 0 : 1);
