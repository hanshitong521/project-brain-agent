import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { existsSync } from "node:fs";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const py = join(root, ".venv", "Scripts", "python.exe");
if (!existsSync(py)) {
	process.stderr.write("project-brain: missing .venv python; run scripts/install-and-demo.ps1\n");
	process.exit(1);
}
const child = spawn(py, ["-u", "-m", "brain_mcp.server"], {
	cwd: root,
	env: {
		...process.env,
		PYTHONPATH: join(root, "src"),
		PYTHONUTF8: "1",
		PYTHONUNBUFFERED: "1",
		PYTHONIOENCODING: "utf-8",
	},
	stdio: "inherit",
	windowsHide: true,
});
child.on("exit", (code, signal) => {
	if (signal) process.exit(1);
	process.exit(code ?? 1);
});
