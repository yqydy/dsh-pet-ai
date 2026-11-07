# Capture the current AI-girl pet window repeatedly (live animation frames).
# Usage: powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/capture_anim.ps1 -Frames 12 -IntervalMs 250 -OutDir <dir> [-Width 680]
param(
  [int]$Frames = 12,
  [int]$IntervalMs = 250,
  [string]$OutDir = "F:\ceshi\dsh-pet-ai-girls\build\shots\live-anim",
  [int]$Width = 680
)
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies @('System.Drawing') @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public class PetAnimCap {
  public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr extra);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT rect);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint flags);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  public static List<IntPtr> FindPet(int width) {
    var found = new List<IntPtr>();
    EnumWindows((h, l) => {
      if (!IsWindowVisible(h)) return true;
      int len = GetWindowTextLength(h); if (len == 0) return true;
      var sb = new StringBuilder(len + 1); GetWindowText(h, sb, sb.Capacity);
      if (sb.ToString().IndexOf("dsh-pet", StringComparison.OrdinalIgnoreCase) < 0) return true;
      RECT r; GetWindowRect(h, out r);
      if ((r.Right - r.Left) == width) found.Add(h);
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static string Capture(IntPtr hWnd, string outPath) {
    RECT r; GetWindowRect(hWnd, out r);
    int w = r.Right - r.Left, h = r.Bottom - r.Top;
    using (var bmp = new System.Drawing.Bitmap(w, h, System.Drawing.Imaging.PixelFormat.Format32bppArgb))
    using (var g = System.Drawing.Graphics.FromImage(bmp)) {
      IntPtr hdc = g.GetHdc();
      PrintWindow(hWnd, hdc, 2);
      g.ReleaseHdc(hdc);
      bmp.Save(outPath, System.Drawing.Imaging.ImageFormat.Png);
    }
    return "ok " + w + "x" + h;
  }
}
"@
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$wins = [PetAnimCap]::FindPet($Width)
if ($wins.Count -eq 0) { Write-Host "NO PET WINDOW of width $Width"; exit 2 }
$h = $wins[0]
Write-Host "capturing window hwnd=$h for $Frames frames every ${IntervalMs}ms"
for ($i = 1; $i -le $Frames; $i++) {
  $file = Join-Path $OutDir ("frame-{0:d2}.png" -f $i)
  $res = [PetAnimCap]::Capture($h, $file)
  Write-Host ("[{0}/{1}] {2} {3}" -f $i, $Frames, $file, $res)
  if ($i -lt $Frames) { Start-Sleep -Milliseconds $IntervalMs }
}
