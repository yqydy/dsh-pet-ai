# Capture every visible dsh-pet desktop window (one per pet) via Win32 PrintWindow.
# Usage: powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/capture_pets.ps1 -OutDir <dir> [-TitleMatch <substring>]
param(
  [string]$OutDir = "F:\ceshi\dsh-pet-ai-girls\build\shots\pets",
  [string]$TitleMatch = "dsh-pet"
)
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies @('System.Drawing') @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public class PetWin {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr extra);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint flags);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }

  public static List<string> List(string needle) {
    var result = new List<string>();
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      int len = GetWindowTextLength(h);
      if (len == 0) return true;
      var sb = new StringBuilder(len + 1);
      GetWindowText(h, sb, sb.Capacity);
      string title = sb.ToString();
      if (needle.Length > 0 && title.IndexOf(needle, StringComparison.OrdinalIgnoreCase) < 0) return true;
      RECT r; GetWindowRect(h, out r);
      result.Add(h.ToInt64() + "\t" + (r.Right - r.Left) + "x" + (r.Bottom - r.Top) + "\t" + title);
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
      bool ok = PrintWindow(hWnd, hdc, 2);
      g.ReleaseHdc(hdc);
      if (!ok) g.CopyFromScreen(r.Left, r.Top, 0, 0, new System.Drawing.Size(w, h));
      bmp.Save(outPath, System.Drawing.Imaging.ImageFormat.Png);
    }
    return "ok " + w + "x" + h;
  }
}
"@
[PetWin]::SetProcessDPIAware()
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$windows = [PetWin]::List($TitleMatch)
Write-Host "=== matched windows: $($windows.Count) ==="
$i = 0
$manifest = @()
foreach ($w in $windows) {
  $parts = $w -split "`t"
  $h = [IntPtr][int64]$parts[0]
  $i++
  $file = Join-Path $OutDir ("pet-{0:d2}.png" -f $i)
  $title = $parts[2]
  $res = [PetWin]::Capture($h, $file)
  $bytes = if (Test-Path $file) { (Get-Item $file).Length } else { 0 }
  Write-Host ("[{0}] hwnd={1} size={2} title={3} -> {4} ({5} bytes, {6})" -f $i, $parts[0], $parts[1], $title, $file, $bytes, $res)
  $manifest += [ordered]@{ index = $i; hwnd = $parts[0]; size = $parts[1]; title = $title; file = $file; bytes = $bytes }
}
$manifestPath = Join-Path $OutDir "windows.json"
$manifest | ConvertTo-Json -Depth 3 | Set-Content -Path $manifestPath -Encoding UTF8
Write-Host "manifest: $manifestPath"
