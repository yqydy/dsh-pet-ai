# verify_shots.ps1 —— 枚举可见窗口并用 Win32 PrintWindow 抓图（只读截图，不改任何被测文件）。
#
# 为什么需要它：DSH Web GUI（http://127.0.0.1:57076/）对未携带 token 的请求返回
#   401 "dsh web authentication required; reopen the URL printed by dsh web."
#   （headless Chrome 因此只能截到 401 页面）。真实桌宠运行在 dsh-pet 桌面模式的
#   Electron 透明窗口里，标题为 "dsh-pet 桌宠（桌面模式）"（每只宠物一个窗口）。
#   本脚本枚举所有可见窗口，抓所有标题匹配 -TitleMatch 的窗口（同标题多窗口逐个抓）。
#
# 用法（必须用 Windows PowerShell：powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...）：
#   powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/verify_shots.ps1 `
#     -TitleMatch "dsh-pet" -OutDir "F:\ceshi\dsh-pet-ai-girls\build\shots\pet-windows" `
#     -JsonOut "F:\ceshi\dsh-pet-ai-girls\build\verify\windows_pet.json"
#   加 -ListOnly 只列窗口不截图。
param(
  [string]$TitleMatch = "dsh-pet",
  [string]$OutDir = "F:\ceshi\dsh-pet-ai-girls\build\shots\pet-windows",
  [string]$JsonOut = "",
  [switch]$ListOnly
)

Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies @('System.Drawing') @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public class WinCap2 {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr extra);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint flags);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }

  public static List<string> ListWindows() {
    var result = new List<string>();
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      int len = GetWindowTextLength(h);
      if (len == 0) return true;
      var sb = new StringBuilder(len + 1);
      GetWindowText(h, sb, sb.Capacity);
      RECT r; GetWindowRect(h, out r);
      result.Add(h.ToInt64() + "\t" + (r.Right - r.Left) + "\t" + (r.Bottom - r.Top) + "\t" + (IsIconic(h) ? "1" : "0") + "\t" + sb.ToString());
      return true;
    }, IntPtr.Zero);
    return result;
  }

  public static string Capture(IntPtr hWnd, string outPath) {
    SetProcessDPIAware();
    RECT r; GetWindowRect(hWnd, out r);
    int w = r.Right - r.Left, h = r.Bottom - r.Top;
    if (w <= 0 || h <= 0) return "bad-size " + w + "x" + h;
    string method = "PrintWindow";
    using (var bmp = new System.Drawing.Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format32bppArgb))
    using (var g = System.Drawing.Graphics.FromImage(bmp)) {
      IntPtr hdc = g.GetHdc();
      bool ok = PrintWindow(hWnd, hdc, 2); // PW_RENDERFULLCONTENT
      g.ReleaseHdc(hdc);
      if (!ok || IsBlank(bmp)) {
        method = "CopyFromScreen";
        try { g.CopyFromScreen(r.Left, r.Top, 0, 0, new System.Drawing.Size(w, h)); } catch { }
      }
      bmp.Save(outPath, System.Drawing.Imaging.ImageFormat.Png);
    }
    return "ok " + w + "x" + h + " via " + method;
  }

  // 粗略判断截图是否全黑/全透明（PrintWindow 对 Chromium 加速层可能抓不到内容）
  static bool IsBlank(System.Drawing.Bitmap bmp) {
    int stepX = Math.Max(1, bmp.Width / 40), stepY = Math.Max(1, bmp.Height / 40);
    int nonBlack = 0, total = 0;
    for (int y = stepY / 2; y < bmp.Height; y += stepY) {
      for (int x = stepX / 2; x < bmp.Width; x += stepX) {
        var c = bmp.GetPixel(x, y);
        total++;
        if (c.A > 3 && (c.R > 8 || c.G > 8 || c.B > 8)) nonBlack++;
      }
    }
    return total > 0 && nonBlack * 100 / total < 1; // 采样点几乎全黑
  }
}
"@

[WinCap2]::SetProcessDPIAware() | Out-Null
$raw = [WinCap2]::ListWindows()
$windows = @()
foreach ($line in $raw) {
  $p = $line -split "`t"
  $windows += [pscustomobject]@{
    handle  = [int64]$p[0]
    width   = [int]$p[1]
    height  = [int]$p[2]
    iconic  = ($p[3] -eq '1')
    title   = if ($p.Length -ge 5) { $p[4] } else { '' }
  }
}

$matched = @($windows | Where-Object { $_.title -like "*$TitleMatch*" })
# 兼容兜底：精确标题含中文括号时 -like 依然可用；若没匹配再按关键字放宽一次
if ($matched.Count -eq 0 -and $TitleMatch -eq 'dsh-pet') {
  $matched = @($windows | Where-Object { $_.title -like '*桌宠*' -or $_.title -like '*dsh*pet*' })
}

$captured = @()
if (-not $ListOnly) {
  New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
  $i = 0
  foreach ($m in $matched) {
    if ($m.iconic) { continue } # 最小化窗口抓不到内容
    $i++
    $safe = ($m.title -replace '[^\w\-\u4e00-\u9fa5]+', '_')
    if ($safe.Length -gt 40) { $safe = $safe.Substring(0, 40) }
    $path = Join-Path $OutDir ('window-{0:D2}-{1}.png' -f $i, $safe)
    $res = [WinCap2]::Capture([IntPtr]$m.handle, $path)
    $bytes = 0
    if (Test-Path $path) { $bytes = (Get-Item $path).Length }
    $captured += [pscustomobject]@{
      index  = $i
      handle = $m.handle
      title  = $m.title
      width  = $m.width
      height = $m.height
      path   = $path
      bytes  = $bytes
      result = $res
    }
  }
}

$out = [pscustomobject]@{
  titleMatch = $TitleMatch
  outDir     = $OutDir
  windows    = $windows
  matched    = $matched.Count
  captured   = $captured
}
$json = $out | ConvertTo-Json -Depth 6
if ($JsonOut -ne '') {
  $dir = Split-Path $JsonOut
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  [System.IO.File]::WriteAllText($JsonOut, $json, (New-Object System.Text.UTF8Encoding($false)))
}
Write-Host $json
