using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;
using System.Windows;

namespace monitoring_wpf.Services
{
    /// <summary>
    /// WPF 가 Python 프로세스를 띄우고 종료를 관리.
    /// 얼굴 인증 후: StartTracking() → Learning_TWM 단독 실행 (시선 커서)
    /// "시작" 클릭:  StartAll()      → Zone_tracker + gesture_control 추가 실행
    /// </summary>
    public class PythonProcessManager
    {
        // 트래킹 프로세스 (Learning_TWM) — WPF 종료 시까지 유지
        private readonly List<Process> _trackingProcs = new();
        // 실험 프로세스 (Zone_tracker, gesture_control) — 실험 종료 시 정리
        private readonly List<Process> _experimentProcs = new();

        // ───────────────────────────────────────────
        //  ★ 환경에 맞게 수정할 부분
        // ───────────────────────────────────────────
        private static readonly string GestureDir =
            @"C:\Users\moble_edu\Downloads\gesture_learning_wpf\gesture_learning\gesture_learning";

        private static string PythonExe
        {
            get
            {
                string venv = Path.Combine(GestureDir, ".venv", "Scripts", "python.exe");
                if (File.Exists(venv)) return venv;
                return "py";
            }
        }

        [DllImport("kernel32.dll")]
        private static extern bool FreeConsole();

        /// <summary>
        /// 얼굴 인증 통과 직후 호출. Learning_TWM 만 띄워서 시선 커서 활성화.
        /// 이후 사용자는 시선만으로 "시작" 버튼을 클릭 가능.
        /// </summary>
        public void StartTracking(string userName)
        {
            string logDir = Path.Combine(GestureDir, "logs");
            Directory.CreateDirectory(logDir);

            Launch("Learning_TWM.py",
                $"--name {userName}",
                Path.Combine(logDir, "learning_twm.log"),
                _trackingProcs);
        }

        /// <summary>
        /// "시작" 버튼 클릭 시 호출. Zone_tracker + gesture_control 만 실행
        /// (Learning_TWM 은 이미 StartTracking 으로 도는 중).
        /// </summary>
        public void StartAll(string userName, bool useRobot, string robotIp, int robotPort)
        {
            string robotArg = useRobot ? "yes" : "no";

            string logDir = Path.Combine(GestureDir, "logs");
            Directory.CreateDirectory(logDir);

            Launch("Zone_tracker.py",
                $"--robot {robotArg} --ip {robotIp} --port {robotPort}",
                Path.Combine(logDir, "zone_tracker.log"),
                _experimentProcs);

            Launch("gesture_control_v6.py",
                $"--robot {robotArg} --ip {robotIp} --port {robotPort} --home no",
                Path.Combine(logDir, "gesture_control.log"),
                _experimentProcs);
        }

        private void Launch(string scriptName, string scriptArgs, string logPath, List<Process> bucket)
        {
            try
            {
                string exe = PythonExe;
                string scriptPath = Path.Combine(GestureDir, scriptName);
                string args = $"-u \"{scriptPath}\" {scriptArgs}";

                var psi = new ProcessStartInfo
                {
                    FileName = exe,
                    Arguments = args,
                    WorkingDirectory = GestureDir,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    StandardOutputEncoding = System.Text.Encoding.UTF8,
                    StandardErrorEncoding = System.Text.Encoding.UTF8,
                };
                psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
                psi.EnvironmentVariables["PYTHONUTF8"] = "1";

                var p = new Process { StartInfo = psi, EnableRaisingEvents = true };

                var logStream = new StreamWriter(
                    new FileStream(logPath, FileMode.Create, FileAccess.Write, FileShare.Read))
                { AutoFlush = true };

                logStream.WriteLine($"[{DateTime.Now:HH:mm:ss}] === {scriptName} 시작 ===");
                logStream.WriteLine($"  CMD: {exe} {args}");
                logStream.WriteLine();

                p.OutputDataReceived += (_, e) => { if (e.Data != null) logStream.WriteLine(e.Data); };
                p.ErrorDataReceived += (_, e) => { if (e.Data != null) logStream.WriteLine("[ERR] " + e.Data); };
                p.Exited += (_, _) => { try { logStream.Close(); } catch { } };

                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                bucket.Add(p);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    $"{scriptName} 실행 실패:\n{ex.Message}\n\n경로: {GestureDir}",
                    "프로세스 실행 오류",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        /// <summary>
        /// 실험 종료: Zone_tracker, gesture_control 만 종료.
        /// Learning_TWM(시선 트래킹) 은 계속 작동.
        /// </summary>
        public void StopExperiment()
        {
            KillProcs(_experimentProcs);
        }

        /// <summary>
        /// WPF 종료: 모든 Python 프로세스 종료.
        /// </summary>
        public void StopAll()
        {
            KillProcs(_experimentProcs);
            KillProcs(_trackingProcs);
        }

        private void KillProcs(List<Process> procs)
        {
            foreach (var p in procs)
            {
                try
                {
                    if (!p.HasExited)
                    {
                        p.Kill(entireProcessTree: true);
                        p.WaitForExit(2000);
                    }
                }
                catch (Exception ex)
                {
                    System.Diagnostics.Debug.WriteLine($"Kill 실패: {ex.Message}");
                }
            }
            procs.Clear();
        }

        /// <summary>
        /// 앱 시작 시 호출: 이전 실행에서 살아남은 좀비 python.exe 청소.
        /// 이 PC 의 모든 python.exe 를 죽이므로 다른 Python 작업과 충돌 주의.
        /// </summary>
        public static void KillZombiePythons()
        {
            try
            {
                foreach (var p in Process.GetProcessesByName("python"))
                {
                    try { p.Kill(entireProcessTree: true); } catch { }
                }
                foreach (var p in Process.GetProcessesByName("pythonw"))
                {
                    try { p.Kill(entireProcessTree: true); } catch { }
                }
            }
            catch { }
        }
    }
}