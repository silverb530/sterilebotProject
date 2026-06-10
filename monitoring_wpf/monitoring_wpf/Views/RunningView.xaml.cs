using monitoring_wpf.service;
using monitoring_wpf.Services;
using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Windows.Threading;

namespace monitoring_wpf.Views
{
    public partial class RunningView : UserControl
    {
        public Action? OnEmergencyStop { get; set; }
        public Action? OnResume { get; set; }
        public Action? OnExit { get; set; }

        private bool _isEmergency = false;
        private bool _isPaused = false;
        private readonly DispatcherTimer _clock = new();

        // 배치도 폴링 — 1초마다 Pi /state 호출 → 시험관 현황 갱신
        private readonly DispatcherTimer _statePoll = new();
        private static readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(3) };
        private const string PiBase = "http://192.168.0.32:5001";

        // Zone_tracker MJPEG 스트림 URL (같은 PC면 localhost, 다른 PC면 그 IP)
        private const string ZoneTrackerStreamUrl = "http://localhost:8090/stream";
        // 제스처 인식 MJPEG 스트림 URL
        private const string GestureStreamUrl = "http://localhost:8091/stream";
        private const int LabCamIndex = 0;
        // ArmCamIndex 는 camera_indices.json 에서 "arm" 키로 동적으로 읽음.
        // 매핑 안 됐으면 -1 → PIP 표시 안 함.
        private static int ArmCamIndex => LoadArmCamIndex();

        /// <summary>
        /// gesture_learning/camera_indices.json 을 찾아서 "arm" 키 값을 반환.
        /// 파일 없거나 키 없으면 -1.
        /// </summary>
        private static int LoadArmCamIndex()
        {
            try
            {
                // exe 위치에서 위로 올라가며 gesture_learning/camera_indices.json 탐색
                var dir = new DirectoryInfo(AppDomain.CurrentDomain.BaseDirectory);
                while (dir != null)
                {
                    var path = System.IO.Path.Combine(dir.FullName, "gesture_learning", "camera_indices.json");
                    if (File.Exists(path))
                    {
                        var json = File.ReadAllText(path);
                        var map = JsonSerializer.Deserialize<Dictionary<string, int>>(json);
                        if (map != null && map.TryGetValue("arm", out int idx))
                            return idx;
                        return -1;
                    }
                    dir = dir.Parent;
                }
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"camera_indices.json 읽기 실패: {ex.Message}");
            }
            return -1;
        }

        private bool _labIsMain = true;
        private bool _isDoorLocked = false;

        public RunningView()
        {
            InitializeComponent();

            _clock.Interval = TimeSpan.FromSeconds(1);
            _clock.Tick += (_, _) => ClockText.Text = DateTime.Now.ToString("HH:mm:ss");
            _clock.Start();

            // 배치도 폴링
            _statePoll.Interval = TimeSpan.FromSeconds(1);
            _statePoll.Tick += async (_, _) => await PollState();

            IsVisibleChanged += async (_, _) =>
            {
                if (IsVisible)
                {
                    StartCameras();
                    _statePoll.Start();
                    // 실험 시작 시 이전 로그 초기화
                    try { await _http.GetAsync($"{PiBase}/clear_log"); }
                    catch { /* Pi 미연결 무시 */ }
                }
                else
                {
                    StopCameras();
                    _statePoll.Stop();
                }
            };
        }

        private void StartCameras() => ApplyCameraLayout();

        private void StopCameras()
        {
            MainCam.Stop();
            PipCam.Stop();
        }

        private void ApplyCameraLayout()
        {
            string mainLbl = _labIsMain ? "실험실 조감캠" : "로봇암 카메라";
            string pipLbl = _labIsMain ? "로봇암 카메라" : "실험실 조감캠";
            Color mainDot = _labIsMain
                ? Color.FromRgb(0x4A, 0xDE, 0x80)
                : Color.FromRgb(0xFB, 0x92, 0x3C);
            Color pipDot = _labIsMain
                ? Color.FromRgb(0xFB, 0x92, 0x3C)
                : Color.FromRgb(0x4A, 0xDE, 0x80);

            MainCam.Stop();
            PipCam.Stop();

            string armMissingLbl = "로봇암 카메라 미연결";

            if (_labIsMain)
            {
                // 큰 화면 = Zone_tracker MJPEG 스트림
                MainCam.StartMjpeg(ZoneTrackerStreamUrl, mainLbl + " 대기 중");

                // 작은 화면 = 제스처 인식 MJPEG 스트림
                PipCam.StartMjpeg(GestureStreamUrl, "손동작 인식 대기 중");
                pipLbl = "손동작 인식";
            }
            else
            {
                // 큰 화면 = 제스처 인식 MJPEG 스트림
                MainCam.StartMjpeg(GestureStreamUrl, "손동작 인식 대기 중");
                mainLbl = "손동작 인식";

                // 작은 화면 = Zone_tracker MJPEG 스트림
                PipCam.StartMjpeg(ZoneTrackerStreamUrl, pipLbl + " 대기 중");
            }

            MainLabelText.Text = mainLbl;
            PipLabelText.Text = pipLbl;
            MainDot.Fill = new SolidColorBrush(mainDot);
            PipDot.Fill = new SolidColorBrush(pipDot);
        }

        private void SwapCameras()
        {
            _labIsMain = !_labIsMain;
            ApplyCameraLayout();
        }

        // ── 클릭 핸들러 ──────────────────────────────
        // 큰 화면(MainCam)은 클릭해도 아무 동작 없음
        private void MainCam_Click(object s, System.Windows.Input.MouseButtonEventArgs e)
        {
            // 아무것도 하지 않음 — 큰 화면 클릭 비활성화
        }

        // 작은 PIP 화면만 클릭 시 전환
        private void PipCam_Click(object s, System.Windows.Input.MouseButtonEventArgs e)
            => SwapCameras();

        // ══════════════════════════════════════════
        // 비상 / 정상 전환
        // ══════════════════════════════════════════
        public void SetEmergency(bool emergency)
        {
            _isEmergency = emergency;

            if (emergency)
            {
                ScenePanel.Visibility = Visibility.Collapsed;
                EmergencyPanel.Visibility = Visibility.Visible;

                BadgeBg.Color = Color.FromRgb(0x7F, 0x1D, 0x1D);
                BadgeDotColor.Color = Color.FromRgb(0xEF, 0x44, 0x44);
                BadgeFg.Color = Color.FromRgb(0xEF, 0x44, 0x44);
                BadgeText.Text = "비상상황 — 중지";

                EstopBorder.Background = new SolidColorBrush(Color.FromRgb(0x7F, 0x1D, 0x1D));
                EstopBorder.BorderBrush = new SolidColorBrush(Color.FromRgb(0xFE, 0xCA, 0xCA));
                EstopIcon.Foreground = new SolidColorBrush(Colors.White);
                EstopIcon.Text = "✓";
                EstopLabel.Foreground = new SolidColorBrush(Colors.White);
                EstopLabel.Text = "정지 해제";

                StatusChip.Background = new SolidColorBrush(Color.FromRgb(0xFE, 0xF2, 0xF2));
                StatusChip.BorderBrush = new SolidColorBrush(Color.FromRgb(0xFC, 0xA5, 0xA5));
                SafetyDot.Fill = new SolidColorBrush(Color.FromRgb(0xDC, 0x26, 0x26));
                StatusLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x7F, 0x1D, 0x1D));
                StatusLabel.Text = "비상상황";
            }
            else
            {
                ScenePanel.Visibility = Visibility.Visible;
                EmergencyPanel.Visibility = Visibility.Collapsed;

                BadgeBg.Color = Color.FromRgb(0x15, 0x80, 0x3D);
                BadgeDotColor.Color = Color.FromRgb(0x4A, 0xDE, 0x80);
                BadgeFg.Color = Color.FromRgb(0x4A, 0xDE, 0x80);
                BadgeText.Text = "실행중";

                EstopBorder.Background = new SolidColorBrush(Color.FromRgb(0xFE, 0xF2, 0xF2));
                EstopBorder.BorderBrush = new SolidColorBrush(Color.FromRgb(0xFC, 0xA5, 0xA5));
                EstopIcon.Foreground = new SolidColorBrush(Color.FromRgb(0xDC, 0x26, 0x26));
                EstopIcon.Text = "⚠";
                EstopLabel.Foreground = new SolidColorBrush(Color.FromRgb(0xDC, 0x26, 0x26));
                EstopLabel.Text = "비상 정지";

                StatusChip.Background = new SolidColorBrush(Color.FromRgb(0xDC, 0xFC, 0xE7));
                StatusChip.BorderBrush = new SolidColorBrush(Color.FromRgb(0x86, 0xEF, 0xAC));
                SafetyDot.Fill = new SolidColorBrush(Color.FromRgb(0x16, 0xA3, 0x4A));
                StatusLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x15, 0x80, 0x3D));
                StatusLabel.Text = "안전";
            }
        }

        // ══════════════════════════════════════════
        // Flask 상태 수신
        // ══════════════════════════════════════════
        public void UpdateState(FlaskState state)
        {
            GasVal.Text = $"{state.Gas:F0}";
            TempVal.Text = $"{state.Temp:F1}";
            HumVal.Text = $"{state.Humidity:F0}";

            GasVal.Foreground = state.Gas > 80
                ? new SolidColorBrush(Color.FromRgb(0xDC, 0x26, 0x26))
                : state.Gas > 50
                    ? new SolidColorBrush(Color.FromRgb(0xD9, 0x77, 0x06))
                    : new SolidColorBrush(Color.FromRgb(0x1E, 0x29, 0x3B));

            if (_isEmergency) return;

            bool warn = state.StatusText.Contains("경고") || state.StatusText.Contains("위험");
            StatusLabel.Text = warn ? "경고" : "안전";
            SafetyDot.Fill = new SolidColorBrush(warn
                ? Color.FromRgb(0xD9, 0x77, 0x06)
                : Color.FromRgb(0x16, 0xA3, 0x4A));
            StatusLabel.Foreground = new SolidColorBrush(warn
                ? Color.FromRgb(0x92, 0x40, 0x0E)
                : Color.FromRgb(0x15, 0x80, 0x3D));
            StatusChip.Background = new SolidColorBrush(warn
                ? Color.FromRgb(0xFF, 0xF7, 0xED)
                : Color.FromRgb(0xDC, 0xFC, 0xE7));
            StatusChip.BorderBrush = new SolidColorBrush(warn
                ? Color.FromRgb(0xFD, 0xBA, 0x74)
                : Color.FromRgb(0x86, 0xEF, 0xAC));
        }

        // ══════════════════════════════════════════
        // 버튼 핸들러
        // ══════════════════════════════════════════
        private void EmergencyStop_Click(object s, System.Windows.Input.MouseButtonEventArgs e)
        {
            if (_isEmergency) OnResume?.Invoke();
            else OnEmergencyStop?.Invoke();
        }

        private void PauseResume_Click(object s, RoutedEventArgs e)
        {
            _isPaused = !_isPaused;
            PauseResumeBtn.Content = _isPaused ? "▶  재  개" : "⏸  일시 정지";
        }

        private void ResetState_Click(object s, RoutedEventArgs e) => OnResume?.Invoke();

        private void DoorLock_Click(object s, RoutedEventArgs e)
        {
            _isDoorLocked = !_isDoorLocked;
            if (BtnDoorLock.Template.FindName("t", BtnDoorLock) is System.Windows.Controls.TextBlock tb)
            {
                tb.Text = _isDoorLocked ? "🔒  외부문 잠금" : "🔓  외부문 잠금해제";
                tb.Foreground = _isDoorLocked
                    ? new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(0xDC, 0x26, 0x26))
                    : new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(0x16, 0xA3, 0x4A));
            }
            if (BtnDoorLock.Parent is System.Windows.Controls.Border parent)
            {
                parent.Background = _isDoorLocked
                    ? new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(0xFE, 0xF2, 0xF2))
                    : new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(0xF0, 0xFD, 0xF4));
                parent.BorderBrush = _isDoorLocked
                    ? new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(0xFC, 0xA5, 0xA5))
                    : new System.Windows.Media.SolidColorBrush(System.Windows.Media.Color.FromRgb(0x86, 0xEF, 0xAC));
            }
        }

        private async void Exit_Click(object s, RoutedEventArgs e)
        {
            // 종료 시 Pi 로그 초기화
            try
            {
                using var http = new System.Net.Http.HttpClient { Timeout = TimeSpan.FromSeconds(3) };
                await http.GetAsync($"{PiBase}/clear_log");
            }
            catch { /* 실패해도 종료는 진행 */ }
            OnExit?.Invoke();
        }

        private async void Reset_Click(object s, RoutedEventArgs e)
        {
            // 확인 다이얼로그
            var result = MessageBox.Show(
                "정말 리셋하시겠습니까?\n\n" +
                "옮긴 시험관이 모두 원래 위치로 되돌아갑니다.\n" +
                "(진행 중 동작이 있으면 완료 후 시작됩니다)",
                "리셋 확인",
                MessageBoxButton.YesNo,
                MessageBoxImage.Question);

            if (result != MessageBoxResult.Yes)
                return;

            // UI 즉시 반영
            SetEmergency(false);
            ClearMapHighlight();

            // Pi 서버의 /reset 엔드포인트 호출 — sterilebot_server.py 가 run_reset() 실행
            try
            {
                using var http = new System.Net.Http.HttpClient
                {
                    Timeout = TimeSpan.FromSeconds(10)
                };
                var resp = await http.GetAsync("http://192.168.0.32:5001/reset");
                string body = await resp.Content.ReadAsStringAsync();
                System.Diagnostics.Debug.WriteLine($"[Reset] /reset 응답: {body}");

                if (!resp.IsSuccessStatusCode)
                {
                    MessageBox.Show($"리셋 요청 실패: {resp.StatusCode}\n{body}",
                                    "리셋 오류",
                                    MessageBoxButton.OK,
                                    MessageBoxImage.Warning);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"리셋 요청 전송 실패: {ex.Message}\n\n" +
                                "Pi 서버(192.168.0.32:5001)가 켜져 있는지 확인하세요.",
                                "리셋 오류",
                                MessageBoxButton.OK,
                                MessageBoxImage.Error);
            }
        }


        // ══════════════════════════════════════════
        // 맵 시험관 하이라이트
        // ══════════════════════════════════════════
        private Ellipse? _lastHighlighted;

        public void HighlightSlot(string slotName)
        {
            ClearMapHighlight();

            var slot = this.FindName($"Slot{slotName}") as Ellipse;
            if (slot != null)
            {
                slot.Fill = new SolidColorBrush(Color.FromRgb(0x22, 0xC5, 0x5E)); // 초록
                slot.Stroke = new SolidColorBrush(Color.FromRgb(0x16, 0xA3, 0x4A));
                slot.StrokeThickness = 3;
                _lastHighlighted = slot;
            }
        }

        public void ClearMapHighlight()
        {
            if (_lastHighlighted != null)
            {
                _lastHighlighted.Fill = new SolidColorBrush(Color.FromRgb(0x3B, 0x82, 0xF6)); // 원래 파란색
                _lastHighlighted.Stroke = new SolidColorBrush(Color.FromRgb(0x25, 0x63, 0xEB));
                _lastHighlighted.StrokeThickness = 1.5;
                _lastHighlighted = null;
            }
        }

        // ══════════════════════════════════════════
        //  배치도 폴링 — Pi /state 받아 슬롯 색 갱신
        // ══════════════════════════════════════════
        private class StateResponse
        {
            [JsonPropertyName("tubes")]
            public Dictionary<string, string>? Tubes { get; set; }
            [JsonPropertyName("holding")]
            public string? Holding { get; set; }
            [JsonPropertyName("busy")]
            public bool Busy { get; set; }
        }

        private async Task PollState()
        {
            try
            {
                var resp = await _http.GetAsync($"{PiBase}/state");
                if (!resp.IsSuccessStatusCode) return;
                var json = await resp.Content.ReadAsStringAsync();
                var data = JsonSerializer.Deserialize<StateResponse>(json);
                if (data?.Tubes == null) return;
                UpdateBatchMap(data);
            }
            catch
            {
                // 네트워크 일시 오류 무시 — 다음 폴링에서 자동 복구
            }
        }

        // ── 슬롯 이름 매핑 (XAML 의 x:Name 과 일치) ──
        //  시약대 (1~4)   : SlotSyak1 ~ SlotSyak4
        //  A 거치대 (1~4) : SlotA1 ~ SlotA4 (화면 표시도 1,2,3,4)
        //  B 거치대 (1~4) : SlotB1 ~ SlotB4 (화면 표시는 거꾸로 4,3,2,1)
        //    ※ B 는 사용자 인식 기준 "1번" 슬롯이 화면 위치상 SlotB4 — 매핑 역순 적용
        private static string BottleSlotName(int n) => $"SlotSyak{n}";

        private static string TubeSlotName(string slot)
        {
            return $"Slot{slot}";   // SlotA1, SlotB3 등 — 직접 매핑
        }

        // ── 색상 ──
        // 시약대용
        private static readonly Color ColorOrigin = Color.FromRgb(0x3B, 0x82, 0xF6);  // 파랑 — 시약대 원위치
        private static readonly Color ColorEmpty = Color.FromRgb(0xCB, 0xD5, 0xE1);  // 회색 — 비어있음 (옮겨짐 표시)
        private static readonly Color ColorHolding = Color.FromRgb(0xF5, 0x9E, 0x0B);  // 주황 — 로봇이 잡은 시험관 자리

        // 시험관 4개를 구분하기 위한 색상 (placed 시 사용)
        private static readonly Color[] TubeColors = new Color[]
        {
            Color.FromRgb(0xEF, 0x44, 0x44),  // tube_1 → 빨강
            Color.FromRgb(0xF5, 0x9E, 0x0B),  // tube_2 → 주황(노랑계열)  ※ Holding 과 비슷하지만 구분됨
            Color.FromRgb(0x10, 0xB9, 0x81),  // tube_3 → 초록(에메랄드)
            Color.FromRgb(0x8B, 0x5C, 0xF6),  // tube_4 → 보라
        };

        private static Color TubeColorOf(string tubeKey)
        {
            // "tube_1" → 인덱스 0
            if (tubeKey.StartsWith("tube_") && int.TryParse(tubeKey.Substring(5), out int n)
                && n >= 1 && n <= 4)
                return TubeColors[n - 1];
            return Color.FromRgb(0x6B, 0x72, 0x80);  // fallback (회색)
        }

        // 슬롯 옆 시험관 번호 라벨 (동적 생성/관리)
        // key = 슬롯명 (예: "A1"), value = 그 슬롯에 띄워둔 TextBlock
        private readonly Dictionary<string, TextBlock> _slotLabels = new();

        private void UpdateBatchMap(StateResponse state)
        {
            var tubes = state.Tubes!;

            // ── 시약대 슬롯 (1~4) ──
            for (int i = 1; i <= 4; i++)
            {
                if (FindName(BottleSlotName(i)) is not Ellipse el) continue;

                string tubeKey = $"tube_{i}";
                if (!tubes.TryGetValue(tubeKey, out var loc)) continue;

                if (loc == $"bottle_{i}")
                    el.Fill = new SolidColorBrush(ColorOrigin);     // 원위치 → 파랑
                else if (loc == "HELD")
                    el.Fill = new SolidColorBrush(ColorHolding);    // 잡힘 → 주황
                else
                    el.Fill = new SolidColorBrush(ColorEmpty);      // 슬롯으로 옮겨짐 → 회색(빈 표시)
            }

            // ── A/B 슬롯 (A1~A4, B1~B4) ──
            //    어떤 시험관이 거기 있는지 역매핑 (server 의 slot 명 기준 — "B1" 등)
            var slotToTube = new Dictionary<string, string>();
            foreach (var kv in tubes)
            {
                var loc = kv.Value;
                if (loc.Length == 2 && (loc[0] == 'A' || loc[0] == 'B') && char.IsDigit(loc[1]))
                    slotToTube[loc] = kv.Key;
            }

            foreach (var slot in new[] { "A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4" })
            {
                string xamlName = TubeSlotName(slot);   // B 는 여기서 역매핑됨
                if (FindName(xamlName) is not Ellipse el) continue;

                // 외부 하이라이트(_lastHighlighted)는 건드리지 않음 (Dwell 강조 보호)
                if (el == _lastHighlighted)
                {
                    EnsureSlotLabel(slot, el, null);    // 라벨도 정리
                    continue;
                }

                if (slotToTube.TryGetValue(slot, out var tube))
                {
                    // 시험관 있음 — 그 시험관 고유 색으로
                    el.Fill = new SolidColorBrush(TubeColorOf(tube));
                    // 번호 라벨 표시 (예: "1" — tube_1 의 1)
                    string num = tube.StartsWith("tube_") ? tube.Substring(5) : tube;
                    EnsureSlotLabel(slot, el, num);
                }
                else
                {
                    // 비어있음 — 회색
                    el.Fill = new SolidColorBrush(ColorEmpty);
                    EnsureSlotLabel(slot, el, null);    // 라벨 제거
                }
            }

            // ── 현재 작업 상태 업데이트 (상세) ──
            if (state.Holding != null)
            {
                string tubeNum = state.Holding.StartsWith("tube_")
                    ? state.Holding.Substring(5) + "번"
                    : state.Holding;
                WorkStatusText.Text = $"🦾 {tubeNum} 시험관 이동 중";
                WorkStatusSub.Text = "그리퍼가 시험관을 잡고 있습니다";
            }
            else if (state.Busy)
            {
                WorkStatusText.Text = "⚙ 로봇 동작 중";
                WorkStatusSub.Text = "로봇팔이 이동하고 있습니다";
            }
            else
            {
                int occupied = 0;
                foreach (var kv in tubes)
                {
                    var loc = kv.Value;
                    if (loc.Length == 2 && (loc[0] == 'A' || loc[0] == 'B') && char.IsDigit(loc[1]))
                        occupied++;
                }
                if (occupied > 0)
                {
                    WorkStatusText.Text = "대기 중";
                    WorkStatusSub.Text = $"거치대 {occupied}개 슬롯 사용 중";
                }
                else
                {
                    WorkStatusText.Text = "대기 중";
                    WorkStatusSub.Text = "시선/제스처로 작업을 시작하세요";
                }
            }
        }

        /// <summary>
        /// 슬롯 옆에 시험관 번호 라벨 생성/갱신/제거.
        /// num == null 이면 라벨 제거. num 이 있으면 슬롯 옆에 작게 표시.
        /// </summary>
        private void EnsureSlotLabel(string slot, Ellipse slotEllipse, string? num)
        {
            // 슬롯 라벨이 들어갈 Canvas 찾기 — slotEllipse 의 부모는 Grid,
            // 그 Grid 의 부모가 Canvas (배치도 캔버스).
            if (slotEllipse.Parent is not Grid slotGrid) return;
            if (slotGrid.Parent is not Canvas canvas) return;

            if (num == null)
            {
                // 라벨 제거
                if (_slotLabels.TryGetValue(slot, out var existing))
                {
                    canvas.Children.Remove(existing);
                    _slotLabels.Remove(slot);
                }
                return;
            }

            // 슬롯 Grid 의 캔버스 좌표
            double left = Canvas.GetLeft(slotGrid);
            double top = Canvas.GetTop(slotGrid);

            // 라벨 위치: 슬롯 우상단 모서리 위에 살짝 띄움
            //   (Width=32 Height=32 슬롯 기준 → 우상단)
            double labelLeft = left + 22;   // 슬롯 우측쯤
            double labelTop = top - 12;   // 슬롯 위로 12

            if (!_slotLabels.TryGetValue(slot, out var tb))
            {
                tb = new TextBlock
                {
                    FontFamily = new FontFamily("Segoe UI"),
                    FontSize = 11,
                    FontWeight = FontWeights.Bold,
                    Foreground = new SolidColorBrush(Color.FromRgb(0x1E, 0x29, 0x3B)),
                    Background = new SolidColorBrush(Color.FromArgb(0xEE, 0xFF, 0xFF, 0xFF)),
                    Padding = new Thickness(3, 0, 3, 0),
                };
                canvas.Children.Add(tb);
                Panel.SetZIndex(tb, 100);   // 다른 요소 위로
                _slotLabels[slot] = tb;
            }

            tb.Text = num;
            Canvas.SetLeft(tb, labelLeft);
            Canvas.SetTop(tb, labelTop);
        }
    }
}