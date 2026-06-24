const { spawn } = require('child_process');
const path = require('path');

// Path to python/ folder containing .pkl files and scripts
const PYTHON_DIR = path.join(__dirname, '../python');
const PYTHON_CMD = process.env.PYTHON_CMD || 'python';

function runPython(script, inputJson, timeoutMs = 720000) {  // 6 minutes
  return new Promise((resolve, reject) => {
    const proc = spawn(PYTHON_CMD, [script], {
      cwd: PYTHON_DIR,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });

    // Kill process if it exceeds timeout
    const timer = setTimeout(() => {
      proc.kill();
      reject(new Error(`${script} timed out after ${timeoutMs/1000}s`));
    }, timeoutMs);

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', d => stdout += d.toString());
    proc.stderr.on('data', d => stderr += d.toString());

    proc.on('close', code => {
      clearTimeout(timer);
      if (code !== 0) {
        return reject(new Error(stderr || `${script} exited with code ${code}`));
      }
      try {
        resolve(JSON.parse(stdout));
      } catch {
        reject(new Error(`Invalid JSON from ${script}: ${stdout.slice(0, 200)}`));
      }
    });

    proc.on('error', err => {
      clearTimeout(timer);
      reject(new Error(`Failed to start ${script}: ${err.message}`));
    });

    proc.stdin.write(JSON.stringify(inputJson));
    proc.stdin.end();
  });
}

module.exports = { runPython };
