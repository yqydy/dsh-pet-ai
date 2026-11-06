# Capture the real DSH desktop window via Win32 PrintWindow (no browser auth needed).
# Usage: pwsh -File tools/capture-window.ps1 [-OutPath <png>] [-TitleMatch <substring>]
param(
  [string]$OutPath = "F:\ceshi\dsh-pet-ai-girls\build\shots\window-capture.png",
  [string]$TitleMatch = ""
)
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies @('System.Drawing') @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public class WinCap {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr extra);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
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
      result.Add(h.ToInt64() + "\t" + (r.Right - r.Left) + "x" + (r.Bottom - r.Top) + "\t" + sb.ToString());
      return true;
    }, IntPtr.Zero);
    return result;
  }

  public static string Capture(IntPtr hWnd, string outPath) {
    SetProcessDPIAware();
    RECT r; GetWindowRect(hWnd, out r);
    int w = r.Right - r.Left, h = r.Bottom - r.Top;
    if (w <= 0 || h <= 0) return "bad-size " + w + "x" + h;
    using (var bmp = new System.Drawing.Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format32bppArgb))
    using (var g = System.Drawing.Graphics.FromImage(bmp)) {
      IntPtr hdc = g.GetHdc();
      bool ok = PrintWindow(hWnd, hdc, 2); // PW_RENDERFULLCONTENT
      g.ReleaseHdc(hdc);
      if (!ok) {
        // fall back: BitBlt from screen
        g.CopyFromScreen(r.Left, r.Top, 0, 0, new System.Drawing.Size(w, h));
      }
      bmp.Save(outPath, System.Drawing.Imaging.ImageFormat.Png);
    }
    return "ok " + w + "x" + h;
  }
}
"@
[WinCap]::SetProcessDPIAware()
$windows = [WinCap]::ListWindows()
Write-Host "=== visible windows ==="
$windows | ForEach-Object { Write-Host $_ }
$target = $null
foreach ($w in $windows) {
  $parts = $w -split "`t"
  $title = $parts[2]
  if ($TitleMatch -and $title -like "*$TitleMatch*") { $target = [IntPtr][int64]$parts[0]; Write-Host "matched: $w"; break }
}
if (-not $target) {
  foreach ($w in $windows) {
    $parts = $w -split "`t"
    if ($parts[2] -match "DeepSeek|DSH|Harness") { $target = [IntPtr][int64]$parts[0]; Write-Host "default match: $w"; break }
  }
}
if (-not $target) { Write-Host "NO WINDOW FOUND"; exit 2 }
New-Item -ItemType Directory -Force -Path (Split-Path $OutPath) | Out-Null
$res = [WinCap]::Capture($target, $OutPath)
Write-Host "capture: $res -> $OutPath"
if (Test-Path $OutPath) { Write-Host "bytes: $((Get-Item $OutPath).Length)" }
