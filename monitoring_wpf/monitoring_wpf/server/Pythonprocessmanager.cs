using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Management;        // ★ NuGet "System.Management" 패키지 필요
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
        // 우리가 띄우는 스크립트 이름들 — 좀비 식별용
        private static readonly string[] OurScripts = new[]
        {
            "Learning_TWM.py",
            "Zone_tracker.py",
            "gesture_control_v6.py",
        };

        // 트래킹 프로세스 (Learning_TWM) — WPF 종료 시까지 유지
        private readonly List<Process> _trackingProcs = new();
        // 실험 프로세스 (Zone_tracker, gesture_control) — 실험 종료 시 정리
        private readonly List<Process> _experimentProcs = new();

        // gesture_learning 폴더 경로 (실행 시 자동 탐색)
        private static readonly string GestureDir = ResolveGestureDir();

        // 생성 시 — 이전 세션에서 살아남은 우리 Python 좀비 자동 청소
        // (이전 WPF 가 비정상 종료되었거나, Kill 이 실패한 경우 대비)
        public PythonProcessManager()
        {
            KillOurPreviousPythons();
        }

        /// <summary>
        /// 명령줄에 우리 스크립트 이름이 포함된 python.exe / pythonw.exe / py.exe 를 모두 죽임.
        /// venv Python, 시스템 Python 구분 없이 — 명령줄만 보고 우리 것이면 정리.
        /// app.py 등 다른 Python 프로세스는 건드리지 않음.
        /// </summary>
        public static void KillOurPreviousPythons()
        {
            // 1단계: WMI 로 우리 스크립트 실행 중인 모든 python 의 PID 수집
            //         (Process.Kill 도중 다른 항목에 영향 없도록 먼저 PID 만 모음)
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
                    catch { /* PID 변환 실패 — 다음 항목으로 */ }
                }
                Debug.WriteLine($"[PythonProcessManager] WMI 조회 — 우리 좀비 후보 {targetPids.Count}개");
            }
            catch (Exception ex)
            {
                Debug.WriteLine($"[PythonProcessManager] WMI 조회 실패 (무시): {ex.Message}");
                return;
            }

            // 2단계: 수집한 PID 들을 하나씩 Kill — 각각 독립된 try/catch
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
                    // 이미 종료됨 — 정상
                    Debug.WriteLine($"[PythonProcessManager] PID {pid} 이미 종료됨 (skip)");
                }
                catch (InvalidOperationException)
                {
                    // 이미 종료됨 — 정상
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

        /// <summary>
        /// exe 위치에서 부모 폴더로 올라가며 gesture_learning 폴더를 찾음.
        /// Learning_TWM.py 가 있는 폴더만 유효한 것으로 간주.
        /// </summary>
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

        /// <summary>
        /// 얼굴 인증 통과 직후 호출. Learning_TWM 만 띄워서 시선 커서 활성화.
        /// </summary>
        public void StartTracking(string userName)
        {
            Launch("Learning_TWM.py",
                $"--name {userName}",
                _trackingProcs);
        }

        /// <summary>
        /// "시작" 버튼 클릭 시 호출. Zone_tracker + gesture_control 실행.
        /// </summary>
        public void StartAll(string userName, bool useRobot, string robotIp, int robotPort)
        {
            string robotArg = useRobot ? "yes" : "no";

            Launch("Zone_tracker.py",
                $"--robot {robotArg} --ip {robotIp} --port {robotPort}",
                _experimentProcs);

            Launch("gesture_control_v6.py",
                $"--robot {robotArg} --ip {robotIp} --port {robotPort} --home no",
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
        }

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
                    Debug.WriteLine($"Kill 실패: {ex.Message}");
                }
            }
            procs.Clear();
        }
    }
}