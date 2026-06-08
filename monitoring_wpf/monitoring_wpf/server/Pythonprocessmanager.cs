using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Management;        // ★ NuGet "System.Management" 패키지 필요
using System.Windows;

namespace monitoring_wpf.Services
{
    public class PythonProcessManager
    {
        private static readonly string[] OurScripts = new[]
        {
            "Learning_TWM.py",
            "Zone_tracker.py",
            "gesture_control_v6.py",
            "app.py",
            "fall_detection.py",  // ★ 추가
        };

        private readonly List<Process> _trackingProcs = new();
        private readonly List<Process> _gestureProcs = new();
        private readonly List<Process> _experimentProcs = new();
        private readonly List<Process> _fallDetectProcs = new();  // ★ 추가

        private static readonly string GestureDir = ResolveGestureDir();
        private static readonly string ServerDir = ResolveServerDir();
        private static readonly string FallDetectDir = @"C:\SterileBot\Fall_detection";  // ★ 추가

        public PythonProcessManager()
        {
            KillOurPreviousPythons();
        }

        public static void KillOurPreviousPythons()
        {
            var targetPids = new List<(int pid, string cmd)>();
            try
            {
                using var searcher = new ManagementObjectSearcher(
                    "SELECT ProcessId, CommandLine FROM Win32_Process " +
                    "WHERE Name = 'python.exe' OR Name = 'pythonw.exe' OR Name = 'py.exe'");

                foreach (ManagementBaseObject obj in searcher.Get())
                {
                    string cmd = obj["CommandLine"] as string ?? "";
                    if (string.IsNullOrEmpty(cmd)) continue;
                    if (!OurScripts.Any(s => cmd.Contains(s))) continue;

                    try
                    {
                        uint pid = (uint)obj["ProcessId"];
                        targetPids.Add(((int)pid, cmd));
                    }
                    catch { }
                }
                Debug.WriteLine($"[PythonProcessManager] WMI 조회 — 우리 좀비 후보 {targetPids.Count}개");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PythonProcessManager] WMI 조회 실패 (무시): {ex.Message}");
                return;
            }

            int killed = 0;
            foreach (var (pid, cmd) in targetPids)
            {
                try
                {
                    var p = Process.GetProcessById(pid);
                    p.Kill(entireProcessTree: true);
                    killed++;
                    Debug.WriteLine($"[PythonProcessManager] 좀비 PID {pid} 정리: {cmd}");
                }
                catch (ArgumentException)
                {
                    Debug.WriteLine($"[PythonProcessManager] PID {pid} 이미 종료됨 (skip)");
                }
                catch (InvalidOperationException)
                {
                    Debug.WriteLine($"[PythonProcessManager] PID {pid} 이미 종료됨 (skip)");
                }
                catch (Exception ex)
                {
                    Debug.WriteLine($"[PythonProcessManager] PID {pid} Kill 실패: {ex.Message}");
                }
            }

            if (targetPids.Count > 0)
                Debug.WriteLine($"[PythonProcessManager] 시작 시 좀비 정리: {killed}/{targetPids.Count}개");
        }

        private static string ResolveGestureDir()
        {
            var dir = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
            while (dir != null)
            {
                var candidate = Path.Combine(dir.FullName, "gesture_learning");
                if (Directory.Exists(candidate) &&
                    File.Exists(Path.Combine(candidate, "Learning_TWM.py")))
                {
                    return candidate;
                }
                dir = dir.Parent;
            }

            MessageBox.Show(
                "gesture_learning 폴더를 찾을 수 없습니다.\n" +
                "프로젝트 루트 아래에 gesture_learning/Learning_TWM.py 가 있어야 합니다.",
                "경로 설정 오류",
                MessageBoxButton.OK, MessageBoxImage.Error);
            return "";
        }

        private static string ResolveServerDir()
        {
            var dir = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
            while (dir != null)
            {
                var candidate = Path.Combine(dir.FullName, "server");
                if (Directory.Exists(candidate) &&
                    File.Exists(Path.Combine(candidate, "app.py")))
                {
                    return candidate;
                }
                dir = dir.Parent;
            }
            Debug.WriteLine("[PythonProcessManager] server/app.py 를 찾을 수 없음 (무시)");
            return "";
        }

        private static string ServerPythonExe
        {
            get
            {
                if (string.IsNullOrEmpty(ServerDir)) return "py";
                string venv = Path.Combine(ServerDir, ".venv", "Scripts", "python.exe");
                if (File.Exists(venv)) return venv;
                return "py";
            }
        }

        private static string PythonExe
        {
            get
            {
                if (string.IsNullOrEmpty(GestureDir)) return "py";
                string venv = Path.Combine(GestureDir, ".venv", "Scripts", "python.exe");
                if (File.Exists(venv)) return venv;
                return "py";
            }
        }

        // ★ Fall detection 전용 Python 실행 파일 (py -3.11 사용)
        private static string FallDetectPythonExe
        {
            get
            {
                string venv = Path.Combine(FallDetectDir, ".venv", "Scripts", "python.exe");
                if (File.Exists(venv)) return venv;
                return "py";
            }
        }

        public void StartFlaskServer()
        {
            if (string.IsNullOrEmpty(ServerDir))
            {
                Debug.WriteLine("[PythonProcessManager] server 폴더 없음 — Flask 자동 실행 건너뜀");
                return;
            }

            string scriptPath = Path.Combine(ServerDir, "app.py");
            if (!File.Exists(scriptPath))
            {
                Debug.WriteLine("[PythonProcessManager] app.py 없음 — Flask 자동 실행 건너뜀");
                return;
            }

            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = ServerPythonExe,
                    Arguments = $"-u \"{scriptPath}\"",
                    WorkingDirectory = ServerDir,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    StandardOutputEncoding = System.Text.Encoding.UTF8,
                    StandardErrorEncoding = System.Text.Encoding.UTF8,
                };
                psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
                psi.EnvironmentVariables["PYTHONUTF8"] = "1";
                psi.EnvironmentVariables["FLASK_DEBUG"] = "0";

                var p = new Process { StartInfo = psi, EnableRaisingEvents = true };
                p.OutputDataReceived += (_, e) =>
                {
                    if (e.Data != null) Debug.WriteLine($"[app.py] {e.Data}");
                };
                p.ErrorDataReceived += (_, e) =>
                {
                    if (e.Data != null) Debug.WriteLine($"[app.py][ERR] {e.Data}");
                };

                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                _trackingProcs.Add(p);
                Debug.WriteLine("[PythonProcessManager] Flask 서버 시작됨");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PythonProcessManager] Flask 시작 실패: {ex.Message}");
            }
        }

        // ★ WPF 시작 시 fall_detection.py 백그라운드 실행
        public void StartFallDetection()
        {
            string scriptPath = Path.Combine(FallDetectDir, "fall_detection.py");

            if (!File.Exists(scriptPath))
            {
                Debug.WriteLine($"[PythonProcessManager] fall_detection.py 없음: {scriptPath}");
                return;
            }

            try
            {
                var psi = new ProcessStartInfo
                {
                    FileName = FallDetectPythonExe,
                    Arguments = $"-u \"{scriptPath}\" --camera 1",
                    WorkingDirectory = FallDetectDir,
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
                p.OutputDataReceived += (_, e) =>
                {
                    if (e.Data != null) Debug.WriteLine($"[fall_detection.py] {e.Data}");
                };
                p.ErrorDataReceived += (_, e) =>
                {
                    if (e.Data != null) Debug.WriteLine($"[fall_detection.py][ERR] {e.Data}");
                };

                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                _fallDetectProcs.Add(p);
                Debug.WriteLine("[PythonProcessManager] fall_detection.py 시작됨");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PythonProcessManager] fall_detection.py 시작 실패: {ex.Message}");
            }
        }

        public void StartTracking(string userName)
        {
            Launch("Learning_TWM.py",
                $"--name {userName}",
                _trackingProcs);
        }

        public void StartGesture()
        {
            Launch("gesture_control_v6.py",
                "--robot no --home no",
                _gestureProcs);
        }

        public void StartAll(string userName, bool useRobot, string robotIp, int robotPort)
        {
            string robotArg = useRobot ? "yes" : "no";

            KillProcs(_gestureProcs);
            Launch("gesture_control_v6.py",
                $"--robot {robotArg} --ip {robotIp} --port {robotPort} --home no",
                _experimentProcs);

            Launch("Zone_tracker.py",
                $"--robot {robotArg} --ip {robotIp} --port {robotPort}",
                _experimentProcs);
        }

        private void Launch(string scriptName, string scriptArgs, List<Process> bucket)
        {
            if (string.IsNullOrEmpty(GestureDir)) return;

            try
            {
                string exe = PythonExe;
                string scriptPath = Path.Combine(GestureDir, scriptName);

                if (!File.Exists(scriptPath))
                {
                    MessageBox.Show(
                        $"{scriptName} 파일을 찾을 수 없습니다.\n경로: {scriptPath}",
                        "스크립트 누락",
                        MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }

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

                p.OutputDataReceived += (_, e) =>
                {
                    if (e.Data != null) Debug.WriteLine($"[{scriptName}] {e.Data}");
                };
                p.ErrorDataReceived += (_, e) =>
                {
                    if (e.Data != null) Debug.WriteLine($"[{scriptName}][ERR] {e.Data}");
                };

                p.Start();
                p.BeginOutputReadLine();
                p.BeginErrorReadLine();
                bucket.Add(p);
            }
            catch (Exception ex)
            {
                MessageBox.Show(
                    $"{scriptName} 실행 실패:\n{ex.Message}",
                    "프로세스 실행 오류",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        public void StopExperiment()
        {
            KillProcs(_experimentProcs);
            Launch("gesture_control_v6.py", "--robot no --home no", _gestureProcs);
        }

        public void StopAll()
        {
            KillProcs(_experimentProcs);
            KillProcs(_gestureProcs);
            KillProcs(_trackingProcs);
            KillProcs(_fallDetectProcs);  // ★ WPF 종료 시 fall_detection.py 함께 종료
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
                    Debug.WriteLine($"Kill 실패: {ex.Message}");
                }
            }
            procs.Clear();
        }
    }
}