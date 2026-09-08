# Tianshen release gate (ADR-029): automatic audit + calibration for every major version.
# Run: Invoke-Expression (Get-Content -Raw tools\audit_gate.ps1)
# Exit 0 = PASS (release allowed); 1 = FAIL (release forbidden).
# NOTE: ASCII-only on purpose (PowerShell 5.1 reads BOM-less .ps1 as ANSI).

$ErrorActionPreference = "Continue"
# ROOT from current location (gate may run via Invoke-Expression; $PSScriptRoot is empty then)
$ROOT = (Get-Location).Path
$PY = Join-Path $ROOT "tools\python\python.exe"
$env:TMP = Join-Path $ROOT ".tmp"
$env:TEMP = $env:TMP
$env:PYTHONUTF8 = "1"
New-Item -ItemType Directory -Force $env:TMP | Out-Null

$report = Join-Path $ROOT "artifacts\audit_gate_report.md"
$results = New-Object System.Collections.Generic.List[object]
$started = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$steps = @(
    @{ Name = "Unit tests";            Cmd = "-m pytest -q" },
    @{ Name = "Calibrate F/P certs";   Cmd = "tools\certify_planes.py" },
    @{ Name = "Calibrate S certs";     Cmd = "tools\certify_meaning.py" },
    @{ Name = "Rebuild word planes";   Cmd = "tools\build_word_planes.py" },
    @{ Name = "Data consistency";      Cmd = "tools\review_v02.py" },
    @{ Name = "Full-system audit";     Cmd = "tools\audit_full.py" },
    @{ Name = "E2E integration";       Cmd = "tools\e2e_check.py" },
    @{ Name = "Eval polyphone";        Cmd = "-m eval.polyphone_bench" },
    @{ Name = "Eval semantic";         Cmd = "-m eval.semantic_bench" },
    @{ Name = "Eval token economy";    Cmd = "-m eval.token_economy" },
    @{ Name = "Threshold gate";        Cmd = "tools\gate_check.py" }
)

$failCount = 0
foreach ($s in $steps) {
    Write-Host "===== [$($s.Name)] ====="
    $args = $s.Cmd -split " "
    & $PY @args *> (Join-Path $ROOT "artifacts\gate_step.log")
    $code = $LASTEXITCODE
    $ok = ($code -eq 0)
    if (-not $ok) { $failCount++ }
    $results.Add([pscustomobject]@{ Name = $s.Name; Pass = $ok; ExitCode = $code })
    Write-Host "     -> $($s.Name): $(if ($ok) { 'PASS' } else { 'FAIL' })"
}

$finished = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$verdict = if ($failCount -eq 0) { "PASS - release allowed" } else { "FAIL - release forbidden" }

$lines = @()
$lines += "# Release Gate Report (ADR-029)"
$lines += ""
$lines += "- Start: $started  End: $finished"
$lines += "- Verdict: **$verdict** (failed steps: $failCount / $($steps.Count))"
$lines += ""
$lines += "| Step | Result |"
$lines += "|---|---|"
foreach ($r in $results) {
    $lines += "| $($r.Name) | $(if ($r.Pass) { 'PASS' } else { 'FAIL (exit ' + $r.ExitCode + ')' }) |"
}
$lines += ""
$lines += "Thresholds (tools/gate_check.py; changes require ADR-029 revision):"
$lines += "- Independence: deep-layer R2(F+P explains S) < 0.3"
$lines += "- Semantic retrieval: S2 Hit@10 >= 0.19"
$lines += "- Polyphone accuracy >= 99.9%"
$lines += "- Rank criterion: every plane measured rank >= 0.8 x nominal"
$lines += "- E2E integration: one text through tokenize -> pinyin -> 3D retrieval -> plug routing (exit 0)"
$lines -join "`n" | Out-File -FilePath $report -Encoding utf8

Write-Host ""
Write-Host "===================="
Write-Host "Gate verdict: $verdict"
Write-Host "Report: $report"
if ($failCount -gt 0) { exit 1 } else { exit 0 }
