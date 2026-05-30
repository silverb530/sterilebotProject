using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
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

        // gesture_learning 폴더 경로 (실행 시 자동 탐색)
        private static readonly string GestureDir = ResolveGestureDir();

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

            // 못 찾았으면 빈 문자열 반환 — Launch 에서 에러 메시지 표시
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
        /// 이후 사용자는 시선만으로 "시작" 버튼을 클릭 가능.
        /// </summary>
        public void StartTracking(string userName)
        {
            Launch("Learning_TWM.py",
                $"--name {userName}",
                _trackingProcs);
        }

        /// <summary>
        /// "시작" 버튼 클릭 시 호출. Zone_tracker + gesture_control 만 실행
        /// (Learning_TWM 은 이미 StartTracking 으로 도는 중).
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

                // Python 의 stdout/stderr 는 Visual Studio 의 [디버그] 출력 창으로
                // (로그 파일은 만들지 않음 — 사람마다 경로/권한 문제 회피)
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
                    Debug.WriteLine($"Kill 실패: {ex.Message}");
                }
            }
            procs.Clear();
        }

        /// <summary>
        /// (정적, 옵션) 시작 시 좀비 python.exe 청소.
        /// 주의: app.py 같은 다른 Python 도 같이 죽이므로 기본적으로 호출 안 함.
        /// 필요 시 수동으로 PowerShell 에서: taskkill /F /IM python.exe
        /// </summary>
        public static void KillZombiePythons()
        {
            try
            {
                foreach (var p in Process.GetProcessesByName("python"))
                    try { p.Kill(entireProcessTree: true); } catch { }
                foreach (var p in Process.GetProcessesByName("pythonw"))
                    try { p.Kill(entireProcessTree: true); } catch { }
            }
            catch { }
        }
    }
}