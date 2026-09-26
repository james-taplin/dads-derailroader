# Added for the author handover. Set environment variables in your PowerShell session.
# No paths point back to James's source workspace or installed game.
$G29Python = if ($env:G29_PYTHON) { $env:G29_PYTHON } else { '' }
$G29Unity = if ($env:G29_UNITY) { $env:G29_UNITY } else { '' }
$G29AssetRipper = if ($env:G29_ASSETRIPPER) { $env:G29_ASSETRIPPER } else { '' }
