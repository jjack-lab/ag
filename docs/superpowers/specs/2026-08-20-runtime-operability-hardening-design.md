# Current-Machine Runtime Operability Hardening Design

## Goal

Improve one-click operation on the current Windows computer so startup failures
are diagnosable and model readiness is visible before services launch. The
existing application behavior, ports, model inference, and optional behavior
model degradation policy remain unchanged.

## Scope

The change covers only:

- persistent stdout and stderr logs for the API and Web development server;
- concise log-tail diagnostics when either service fails readiness checks;
- detector and behavior artifact metadata in the Python preflight JSON;
- user-facing startup output that identifies the log directory;
- documentation and automated regression coverage for these contracts.

The following remain out of scope:

- portable packaging for other computers;
- automatic Python, Node.js, or dependency installation;
- changing ports 8000 or 5173;
- opening firewall access or exposing the Web server to the LAN;
- eager behavior-model construction or inference during startup;
- making the optional behavior model a startup requirement.

## Runtime Architecture

`start_delivery.ps1` remains the single orchestration entry point. Before
launching child processes it creates `data/logs` and assigns four stable log
files:

- `api.stdout.log`
- `api.stderr.log`
- `web.stdout.log`
- `web.stderr.log`

Each new start attempt replaces the previous content of these four current-run
logs. The processes stay hidden as they are today, but `Start-Process` redirects
their output to the matching files. The process-state file keeps only ownership
and PID information; logs are intentionally retained after stop so a failed run
can be diagnosed.

When readiness succeeds, the script prints the Web URL, API URL, stop command,
and log directory. When readiness fails, it stops only the recorded delivery
process tree, prints a bounded tail from every nonempty log, and exits with the
existing nonzero status. Log-read errors must not hide the original startup
failure.

## Preflight Model Reporting

`scripts/preflight.py` continues to load and verify the detector because the
detector is mandatory. It additionally calls the existing behavior artifact
resolver and emits these JSON fields:

- `detector_status`, `detector_path`, `detector_sha256`;
- `behavior_status`, `behavior_path`, `behavior_sha256`;
- `behavior_error` when the resolver reports the artifact as unavailable.

The legacy `model_sha256` detector field remains for compatibility.

The preflight does not instantiate X3D or run inference. A missing behavior
checkpoint is reported as `unavailable` but the preflight still exits zero,
preserving detector-only operation. Actual checkpoint construction remains lazy
on the first video job.

## Error Handling

- Failure to create or open the log directory is a startup error with the exact
  path in the diagnostic.
- Child-process readiness failure remains a startup error.
- Failure to read a diagnostic log is reported as a secondary warning and does
  not replace the primary startup error.
- Missing behavior weights remain nonfatal.
- Detector, Python dependency, npm, Vite dependency, port-occupancy, and PID
  ownership checks keep their current behavior.

## Testing

Implementation follows TDD and adds focused tests for:

1. preflight JSON containing detector and behavior artifact metadata;
2. missing behavior weights producing `unavailable` while preflight succeeds;
3. startup script defining four redirected logs and bounded failure tails;
4. successful real start exposing HTTP 200/`status: ok`, producing log files,
   and printing the log directory;
5. stop removing the process-state file and releasing both ports;
6. complete Python and React regressions plus the production Web build.

## Success Criteria

- Double-click startup remains compatible with the current configured Python.
- A normal start and stop cycle succeeds on this computer.
- Operators can find API and Web stdout/stderr under `data/logs`.
- A child startup failure yields actionable bounded log output.
- Preflight clearly reports both model artifacts without making behavior weights
  mandatory.
- Existing image/video recognition and detector-only degradation contracts do
  not change.
