#Requires -Version 5.1

[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputFileName = 'study_notes_index.html'
$outputPath = Join-Path $root $outputFileName

function ConvertTo-HtmlText {
    param([AllowNull()][string]$Value)

    if ($null -eq $Value) {
        return ''
    }

    return [System.Net.WebUtility]::HtmlEncode($Value)
}

function ConvertTo-UrlPath {
    param([string]$RelativePath)

    return (($RelativePath -split '/') | ForEach-Object {
        [System.Uri]::EscapeDataString($_)
    }) -join '/'
}

function Get-PageTitle {
    param([System.IO.FileInfo]$File)

    $content = [System.IO.File]::ReadAllText($File.FullName, [System.Text.Encoding]::UTF8)
    $match = [regex]::Match(
        $content,
        '<title\b[^>]*>(.*?)</title>',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase -bor
        [System.Text.RegularExpressions.RegexOptions]::Singleline
    )

    if ($match.Success) {
        $title = [System.Net.WebUtility]::HtmlDecode($match.Groups[1].Value)
        $title = [regex]::Replace($title, '\s+', ' ').Trim()
        if ($title) {
            return $title
        }
    }

    return $File.BaseName
}

function New-TreeNode {
    return [pscustomobject]@{
        Directories = [ordered]@{}
        Files       = New-Object System.Collections.ArrayList
    }
}

function Render-Tree {
    param($Node)

    $lines = New-Object System.Collections.Generic.List[string]

    foreach ($directoryName in @($Node.Directories.Keys | Sort-Object)) {
        $directoryNode = $Node.Directories[$directoryName]
        [void]$lines.Add('<li class="tree-directory">')
        [void]$lines.Add(('  <div class="directory-name"><span class="directory-icon" aria-hidden="true">&#x25B8;</span>{0}</div>' -f (ConvertTo-HtmlText $directoryName)))

        $children = @(Render-Tree $directoryNode)
        if ($children.Count -gt 0) {
            [void]$lines.Add('  <ul>')
            foreach ($child in $children) {
                [void]$lines.Add(('    {0}' -f $child))
            }
            [void]$lines.Add('  </ul>')
        }

        [void]$lines.Add('</li>')
    }

    foreach ($fileEntry in @($Node.Files | Sort-Object Name)) {
        [void]$lines.Add(('  <li class="tree-file"><a href="{0}"><span class="file-title">{1}</span><span class="file-name">{2}</span></a></li>' -f
            (ConvertTo-HtmlText $fileEntry.Href),
            (ConvertTo-HtmlText $fileEntry.Title),
            (ConvertTo-HtmlText $fileEntry.Name)))
    }

    return $lines
}

$rootNode = New-TreeNode
$files = @(
    Get-ChildItem -LiteralPath $root -Recurse -File -Filter '*.html' |
        Where-Object { $_.FullName -ne $outputPath } |
        Sort-Object FullName
)

foreach ($file in $files) {
    $relativePath = $file.FullName.Substring($root.Length).TrimStart('\') -replace '\\', '/'
    $segments = $relativePath -split '/'
    $node = $rootNode

    for ($index = 0; $index -lt ($segments.Length - 1); $index++) {
        $directoryName = $segments[$index]
        if (-not $node.Directories.Contains($directoryName)) {
            $node.Directories[$directoryName] = New-TreeNode
        }
        $node = $node.Directories[$directoryName]
    }

    [void]$node.Files.Add([pscustomobject]@{
        Name         = $segments[-1]
        Title        = Get-PageTitle $file
        RelativePath = $relativePath
        Href         = ConvertTo-UrlPath $relativePath
    })
}

$treeLines = @(Render-Tree $rootNode)
if ($treeLines.Count -eq 0) {
    $treeHtml = '<li class="empty-state">&#x6682;&#x65E0; HTML &#x7B14;&#x8BB0;&#x3002;&#x5C06;&#x6587;&#x7AE0;&#x653E;&#x5165; study_notes &#x7684;&#x4EFB;&#x610F;&#x5B50;&#x76EE;&#x5F55;&#x540E;&#xFF0C;&#x518D;&#x53CC;&#x51FB;&#x8FD0;&#x884C; make_study_notes_index.bat&#x3002;</li>'
} else {
    $treeHtml = $treeLines -join [Environment]::NewLine
}

$generatedAt = Get-Date -Format 'yyyy-MM-dd HH:mm'
$template = @"
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="swordll80.github.io &#x4E2A;&#x4EBA;&#x5B66;&#x4E60;&#x7B14;&#x8BB0;&#x4E0E;&#x6587;&#x7AE0;&#x76EE;&#x5F55;&#x3002">
  <title>&#x5B66;&#x4E60;&#x7B14;&#x8BB0; &middot; swordll80.github.io</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #1f2937;
      --muted: #667085;
      --line: #e5e7eb;
      --soft: #f7f9fc;
      --accent: #2f6fed;
      --accent-soft: #eef4ff;
      --shadow: 0 12px 32px rgba(31, 41, 55, .08);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: #fff;
      color: var(--ink);
      font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
      line-height: 1.7;
    }
    a { color: inherit; }
    .site-header {
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, .94);
    }
    .header-inner, .container, .site-footer {
      width: min(1080px, calc(100% - 40px));
      margin: 0 auto;
    }
    .header-inner {
      min-height: 72px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
    }
    .brand {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
    }
    .brand-mark {
      width: 36px;
      height: 36px;
      display: grid;
      place-items: center;
      border-radius: 11px;
      background: var(--accent);
      color: #fff;
      font-weight: 700;
    }
    .brand strong, .brand em { display: block; }
    .brand strong { font-size: 16px; }
    .brand em { color: var(--muted); font-size: 12px; font-style: normal; }
    .back-link {
      color: var(--accent);
      font-size: 14px;
      text-decoration: none;
    }
    .container { padding: 56px 0 72px; }
    .eyebrow {
      margin: 0 0 8px;
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    h1, h2, p { margin-top: 0; }
    h1 { margin-bottom: 12px; font-size: clamp(32px, 5vw, 48px); line-height: 1.2; }
    .intro-text { max-width: 680px; margin-bottom: 16px; color: var(--muted); }
    .meta { color: var(--muted); font-size: 13px; }
    .note-card {
      margin-top: 32px;
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: #fff;
      box-shadow: var(--shadow);
    }
    .note-card h2 { margin-bottom: 18px; font-size: 20px; }
    .tree, .tree ul { list-style: none; margin: 0; padding: 0; }
    .tree ul { margin: 6px 0 0 18px; padding-left: 18px; border-left: 1px solid var(--line); }
    .tree-directory { margin: 10px 0; }
    .directory-name {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 34px;
      padding: 3px 10px;
      border-radius: 9px;
      background: var(--accent-soft);
      color: #2454ae;
      font-weight: 700;
    }
    .directory-icon { color: var(--accent); font-size: 13px; }
    .tree-file { margin: 4px 0; }
    .tree-file a {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 18px;
      padding: 8px 10px;
      border-radius: 9px;
      text-decoration: none;
    }
    .tree-file a:hover { background: var(--soft); color: var(--accent); }
    .file-title { min-width: 0; overflow-wrap: anywhere; }
    .file-name { color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
    .empty-state { color: var(--muted); }
    .site-footer {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 20px 0 28px;
      border-top: 1px solid var(--line);
      color: var(--muted);
      font-size: 13px;
    }
    @media (max-width: 640px) {
      .header-inner, .container, .site-footer { width: min(100% - 28px, 1080px); }
      .header-inner { min-height: 64px; }
      .brand em { display: none; }
      .container { padding: 40px 0 52px; }
      .note-card { padding: 20px 16px; }
      .tree ul { margin-left: 8px; padding-left: 12px; }
      .tree-file a { display: block; }
      .file-name { display: block; margin-top: 2px; }
      .site-footer { display: block; }
      .site-footer span { display: block; margin-top: 4px; }
    }
  </style>
</head>
<body>
  <header class="site-header">
    <div class="header-inner">
      <a class="brand" href="../index.html">
        <span class="brand-mark" aria-hidden="true">S</span>
        <span>
          <strong>swordll80.github.io</strong>
          <em>&#x4E2A;&#x4EBA;&#x5DE5;&#x5177;&#x4E0E;&#x6280;&#x672F;&#x7B14;&#x8BB0;</em>
        </span>
      </a>
      <a class="back-link" href="../index.html">&#x8FD4;&#x56DE;&#x4E3B;&#x9875;</a>
    </div>
  </header>

  <main class="container">
    <section>
      <p class="eyebrow">Study Notes</p>
      <h1>&#x5B66;&#x4E60;&#x7B14;&#x8BB0;</h1>
      <p class="intro-text">&#x8BB0;&#x5F55;&#x5B66;&#x4E60;&#x8FC7;&#x7A0B;&#x4E2D;&#x7684;&#x77E5;&#x8BC6;&#x6574;&#x7406;&#x3001;&#x5B9E;&#x8DF5;&#x7ECF;&#x9A8C;&#x4E0E;&#x4E3B;&#x9898;&#x5206;&#x4EAB;&#x3002;&#x76EE;&#x5F55;&#x4F1A;&#x6839;&#x636E; study_notes &#x4E2D;&#x7684; HTML &#x6587;&#x4EF6;&#x81EA;&#x52A8;&#x66F4;&#x65B0;&#x3002;</p>
      <p class="meta">&#x5171; $($files.Count) &#x7BC7; &middot; &#x6700;&#x8FD1;&#x66F4;&#x65B0; $generatedAt</p>
    </section>

    <section class="note-card" aria-labelledby="note-directory-title">
      <h2 id="note-directory-title">&#x7B14;&#x8BB0;&#x76EE;&#x5F55;</h2>
      <ul class="tree">
$treeHtml
      </ul>
    </section>
  </main>

  <footer class="site-footer">
    <span>&copy; swordll80.github.io</span>
    <span>&#x8F7B;&#x91CF;&#x9759;&#x6001;&#x7AD9;&#x70B9; &middot; &#x539F;&#x751F; HTML/CSS/JS</span>
  </footer>
</body>
</html>
"@

$utf8NoBom = New-Object -TypeName System.Text.UTF8Encoding -ArgumentList $false
[System.IO.File]::WriteAllText($outputPath, $template, $utf8NoBom)

Write-Host ("Updated: {0}" -f $outputPath)
Write-Host ("Collected {0} HTML note(s)." -f $files.Count)
