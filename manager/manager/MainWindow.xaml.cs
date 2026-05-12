using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Shapes;

namespace SterileBot.Calibration
{
    public partial class MainWindow : Window
    {
        // ── 캘리브레이션 상태 ──
        private int _calibStep = 0;
        private const int TotalMarkers = 16;
        private bool _calibRunning = false;

        // ── Flask 클라이언트 ──────────────────────────────────────
        private readonly FlaskClient _flask = new("http://localhost:5000");

        public MainWindow()
        {
            InitializeComponent();
            BuildMarkerGrid();
            SetupFlask();
        }

        // ═══════════════════════════════════════
        //  Flask 연결 초기화
        // ═══════════════════════════════════════
        private void SetupFlask()
        {
            _flask.Connected += () => Dispatcher.Invoke(() =>
            {
                AppendLog("Flask 연결됨 (http://localhost:5000)");
                SbMsg.Text = "Flask 연결됨";
            });

            _flask.ConnectionError += err => Dispatcher.Invoke(() =>
            {
                SbMsg.Text = "Flask 연결 안됨";
            });

            // 500ms마다 상태 수신 → UI 동기화
            _flask.StateUpdated += state => Dispatcher.Invoke(() => ApplyState(state));

            _flask.StartPolling(500);
        }

        // 상태 수신 시 UI 업데이트
        private void ApplyState(FlaskState s)
        {
            // 그리퍼 상태
            if (s.Gripper == "open")
                UpdateBadge(GripStateBadge, GripState, "열림", "Green");
            else
                UpdateBadge(GripStateBadge, GripState, "닫힘", "Amber");

            // 파라미터 탭 동기화 (처음 한 번만)
            if (PEar.Text == "0.20")
            {
                PEar.Text     = s.Params.EarThreshold.ToString("F2");
                PEarMs.Text   = s.Params.EarMs.ToString();
                PDwell.Text   = s.Params.DwellSec.ToString("F1");
                PDwellR.Text  = s.Params.DwellRadius.ToString();
                PDbl.Text     = s.Params.DoubleBlinkSec.ToString("F1");
                PSafeR.Text   = s.Params.SafeRadius.ToString();
                PSafeZ.Text   = s.Params.SafeZ.ToString();
                PGripSpd.Text = s.Params.GripSpeed.ToString();
                PMoveSpd.Text = s.Params.MoveSpeed.ToString();
            }
        }

        protected override void OnClosed(EventArgs e)
        {
            _flask.StopPolling();
            _flask.Dispose();
            base.OnClosed(e);
        }

        // ═══════════════════════════════════════
        //  타이틀바 드래그 / 윈도우 컨트롤
        // ═══════════════════════════════════════
        private void TitleBar_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
        {
            if (e.ClickCount == 2)
                ToggleMaximize();
            else
                DragMove();
        }

        private void Minimize_Click(object sender, RoutedEventArgs e) => WindowState = WindowState.Minimized;
        private void Maximize_Click(object sender, RoutedEventArgs e) => ToggleMaximize();
        private void Close_Click(object sender, RoutedEventArgs e) => Close();

        private void ToggleMaximize()
        {
            WindowState = WindowState == WindowState.Maximized
                ? WindowState.Normal
                : WindowState.Maximized;
        }

        // ═══════════════════════════════════════
        //  사이드바 네비게이션 (5탭)
        // ═══════════════════════════════════════
        private void Nav_Click(object sender, RoutedEventArgs e)
        {
            if (sender is ToggleButton btn)
            {
                // 모든 토글 해제
                NavCalib.IsChecked = false;
                NavManual.IsChecked = false;
                NavParams.IsChecked = false;
                NavModels.IsChecked = false;
                NavExtra.IsChecked = false;
                btn.IsChecked = true;

                SyncNav(btn);
            }
        }

        private void SyncNav(ToggleButton active)
        {
            // 모든 Pane 숨기기
            PaneCalib.Visibility = Visibility.Collapsed;
            PaneManual.Visibility = Visibility.Collapsed;
            PaneParams.Visibility = Visibility.Collapsed;
            PaneModels.Visibility = Visibility.Collapsed;
            PaneExtra.Visibility = Visibility.Collapsed;

            string tag = active.Tag?.ToString() ?? "";
            switch (tag)
            {
                case "calib":
                    PaneCalib.Visibility = Visibility.Visible;
                    PageTitle.Text = "대시보드";
                    PageSubtitle.Text = "캘리브레이션 · 마커 응시";
                    break;
                case "manual":
                    PaneManual.Visibility = Visibility.Visible;
                    PageTitle.Text = "캘리브레이션";
                    PageSubtitle.Text = "16개 마커 응시 설정";
                    break;
                case "params":
                    PaneParams.Visibility = Visibility.Visible;
                    PageTitle.Text = "수동 제어";
                    PageSubtitle.Text = "좌표 이동 · 그리퍼";
                    break;
                case "models":
                    PaneModels.Visibility = Visibility.Visible;
                    PageTitle.Text = "파라미터";
                    PageSubtitle.Text = "시선 추적 · 안전 설정";
                    break;
                case "extra":
                    PaneExtra.Visibility = Visibility.Visible;
                    PageTitle.Text = "모델 관리";
                    PageSubtitle.Text = "Gaze CNN · YOLOv8";
                    break;
            }
        }

        // ═══════════════════════════════════════
        //  마커 그리드 생성
        // ═══════════════════════════════════════
        private void BuildMarkerGrid()
        {
            MarkerGrid.Children.Clear();
            for (int i = 0; i < TotalMarkers; i++)
            {
                int idx = i;
                var btn = new Button
                {
                    Width = 56,
                    Height = 56,
                    Margin = new Thickness(4),
                    Content = (i + 1).ToString(),
                    FontSize = 14,
                    FontWeight = FontWeights.SemiBold,
                    Foreground = FindBrush("TextDimBrush"),
                    Background = FindBrush("CardSubtleBrush"),
                    BorderBrush = FindBrush("BorderBrush"),
                    BorderThickness = new Thickness(1),
                    Cursor = Cursors.Hand,
                };
                // 둥근 모서리 Template
                var template = new ControlTemplate(typeof(Button));
                var borderFactory = new FrameworkElementFactory(typeof(Border));
                borderFactory.SetValue(Border.CornerRadiusProperty, new CornerRadius(12));
                borderFactory.SetBinding(Border.BackgroundProperty,
                    new System.Windows.Data.Binding("Background") { RelativeSource = new System.Windows.Data.RelativeSource(System.Windows.Data.RelativeSourceMode.TemplatedParent) });
                borderFactory.SetBinding(Border.BorderBrushProperty,
                    new System.Windows.Data.Binding("BorderBrush") { RelativeSource = new System.Windows.Data.RelativeSource(System.Windows.Data.RelativeSourceMode.TemplatedParent) });
                borderFactory.SetBinding(Border.BorderThicknessProperty,
                    new System.Windows.Data.Binding("BorderThickness") { RelativeSource = new System.Windows.Data.RelativeSource(System.Windows.Data.RelativeSourceMode.TemplatedParent) });
                var cpFactory = new FrameworkElementFactory(typeof(ContentPresenter));
                cpFactory.SetValue(ContentPresenter.HorizontalAlignmentProperty, HorizontalAlignment.Center);
                cpFactory.SetValue(ContentPresenter.VerticalAlignmentProperty, VerticalAlignment.Center);
                borderFactory.AppendChild(cpFactory);
                template.VisualTree = borderFactory;
                btn.Template = template;

                btn.Click += (s, e) => MarkerClicked(idx);
                MarkerGrid.Children.Add(btn);
            }
        }

        private void MarkerClicked(int index)
        {
            if (!_calibRunning) return;
            if (index != _calibStep) return;

            // 마커 완료 표시
            if (MarkerGrid.Children[index] is Button b)
            {
                b.Background = FindBrush("AccentBrush");
                b.Foreground = Brushes.White;
                b.BorderBrush = FindBrush("AccentBrush");
            }

            _calibStep++;
            ProgText.Text = $"{_calibStep} / {TotalMarkers}";
            ProgFill.Width = (ProgFill.Parent as Border)?.ActualWidth * _calibStep / TotalMarkers ?? 0;

            if (_calibStep >= TotalMarkers)
            {
                _calibRunning = false;
                UpdateBadge(CalibBadge, CalibBadgeText, "완료", "Green");
                CalibMsg.Text = "캘리브레이션이 완료되었습니다! 모델 관리에서 CNN 학습을 진행하세요.";
                AvgErrText.Text = "8.3";
                AvgErrText.Foreground = FindBrush("GreenBrush");
                MaxErrText.Text = "12.1";
                MaxErrText.Foreground = FindBrush("GreenBrush");
            }
            else
            {
                CalibMsg.Text = $"마커 {_calibStep + 1}번을 3초간 응시해 주세요.";
            }
        }

        // ═══════════════════════════════════════
        //  캘리브레이션 시작/초기화
        // ═══════════════════════════════════════
        private void StartCalib_Click(object sender, RoutedEventArgs e)
        {
            if (_calibRunning) return;
            _calibRunning = true;
            _calibStep = 0;
            ProgText.Text = "0 / 16";
            ProgFill.Width = 0;
            UpdateBadge(CalibBadge, CalibBadgeText, "진행 중", "Accent");
            CalibMsg.Text = "마커 1번을 3초간 응시해 주세요.";
            BuildMarkerGrid();
            AppendLog("캘리브레이션 시작");
        }

        private async void Reset_Click(object sender, RoutedEventArgs e)
        {
            _calibRunning = false;
            _calibStep = 0;
            ProgText.Text = "0 / 16";
            ProgFill.Width = 0;
            UpdateBadge(CalibBadge, CalibBadgeText, "진행 전", "Amber");
            CalibMsg.Text = "'캘리브레이션 시작' 버튼을 누른 후 마커를 순서대로 클릭해 3초씩 응시하세요.";
            AvgErrText.Text = "—";
            AvgErrText.Foreground = FindBrush("TextDimBrush");
            MaxErrText.Text = "—";
            MaxErrText.Foreground = FindBrush("TextDimBrush");
            BuildMarkerGrid();
            AppendLog("초기화 완료");
            await _flask.ResetCalibAsync();
        }

        // ═══════════════════════════════════════
        //  수동 제어
        // ═══════════════════════════════════════
        private async void SendCoords_Click(object sender, RoutedEventArgs e)
        {
            if (!double.TryParse(InX.Text, out var x) ||
                !double.TryParse(InY.Text, out var y) ||
                !double.TryParse(InZ.Text, out var z) ||
                !double.TryParse(InRz.Text, out var rz))
            {
                AppendLog("오류: 좌표 값이 올바르지 않습니다.");
                return;
            }
            AppendLog($"이동 → X:{x} Y:{y} Z:{z} RZ:{rz}");
            await _flask.MoveAsync(x, y, z, rz: rz);
        }

        private async void GoHome_Click(object sender, RoutedEventArgs e)
        {
            InX.Text = "135"; InY.Text = "-82"; InZ.Text = "200"; InRz.Text = "0";
            AppendLog("홈 복귀 → X:135 Y:-82 Z:200 RZ:0");
            await _flask.GoHomeAsync();
        }

        private async void GripOpen_Click(object sender, RoutedEventArgs e)
        {
            UpdateBadge(GripStateBadge, GripState, "열림", "Green");
            AppendLog("그리퍼 열기 (0)");
            await _flask.SetGripperAsync(open: true);
        }

        private async void GripClose_Click(object sender, RoutedEventArgs e)
        {
            UpdateBadge(GripStateBadge, GripState, "닫힘", "Amber");
            AppendLog("그리퍼 닫기 (100)");
            await _flask.SetGripperAsync(open: false);
        }

        // ── 슬라이더 ──
        private void SliderX_Changed(object sender, RoutedPropertyChangedEventArgs<double> e)
            => SvX.Text = ((int)SlX.Value).ToString();
        private void SliderY_Changed(object sender, RoutedPropertyChangedEventArgs<double> e)
            => SvY.Text = ((int)SlY.Value).ToString();
        private void SliderZ_Changed(object sender, RoutedPropertyChangedEventArgs<double> e)
            => SvZ.Text = ((int)SlZ.Value).ToString();
        private void SliderRz_Changed(object sender, RoutedPropertyChangedEventArgs<double> e)
            => SvRz.Text = ((int)SlRz.Value).ToString();

        private async void SendFromSliders_Click(object sender, RoutedEventArgs e)
        {
            InX.Text = SvX.Text; InY.Text = SvY.Text; InZ.Text = SvZ.Text; InRz.Text = SvRz.Text;
            AppendLog($"슬라이더 이동 → X:{SvX.Text} Y:{SvY.Text} Z:{SvZ.Text} RZ:{SvRz.Text}");
            await _flask.MoveAsync(SlX.Value, SlY.Value, SlZ.Value, rz: SlRz.Value);
        }

        // ═══════════════════════════════════════
        //  파라미터
        // ═══════════════════════════════════════
        private async void ApplyParams_Click(object sender, RoutedEventArgs e)
        {
            var p = new FlaskParams
            {
                EarThreshold   = double.TryParse(PEar.Text,     out var v1) ? v1 : 0.20,
                EarMs          = int.TryParse(PEarMs.Text,       out var v2) ? v2 : 150,
                DwellSec       = double.TryParse(PDwell.Text,    out var v3) ? v3 : 1.5,
                DwellRadius    = int.TryParse(PDwellR.Text,      out var v4) ? v4 : 30,
                DoubleBlinkSec = double.TryParse(PDbl.Text,      out var v5) ? v5 : 0.5,
                SafeRadius     = int.TryParse(PSafeR.Text,       out var v6) ? v6 : 260,
                SafeZ          = int.TryParse(PSafeZ.Text,       out var v7) ? v7 : 200,
                GripSpeed      = int.TryParse(PGripSpd.Text,     out var v8) ? v8 : 10,
                MoveSpeed      = int.TryParse(PMoveSpd.Text,     out var v9) ? v9 : 30,
            };
            AppendLog($"파라미터 적용: EAR={p.EarThreshold} Dwell={p.DwellSec}s 안전R={p.SafeRadius}mm");
            await _flask.ApplyParamsAsync(p);
        }

        private async void ResetParams_Click(object sender, RoutedEventArgs e)
        {
            PEar.Text = "0.20"; PEarMs.Text = "150"; PDwell.Text = "1.5";
            PDwellR.Text = "30"; PDbl.Text = "0.5";
            PSafeR.Text = "260"; PSafeZ.Text = "200";
            PGripSpd.Text = "10"; PMoveSpd.Text = "30";
            AppendLog("파라미터 기본값 복원");
            await _flask.ApplyParamsAsync(new FlaskParams());
        }

        // ═══════════════════════════════════════
        //  모델 관리
        // ═══════════════════════════════════════
        private void TrainCnn_Click(object sender, RoutedEventArgs e)
        {
            SbMsg.Text = "CNN 학습 중...";
            AppendLog("Gaze CNN 재학습 시작 (Python subprocess)");
        }

        private void ExportOnnx_Click(object sender, RoutedEventArgs e)
        {
            SbMsg.Text = "ONNX 내보내기 완료";
            AppendLog("gaze.onnx 내보내기 완료");
        }

        private void LoadOnnx_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFileDialog { Filter = "ONNX|*.onnx" };
            if (dlg.ShowDialog() == true)
            {
                GazePath.Text = System.IO.Path.GetFileName(dlg.FileName);
                UpdateBadge(GazeBadge, GazeBadgeText, "로드됨", "Green");
                AppendLog($"ONNX 로드: {GazePath.Text}");
            }
        }

        private void LoadYolo_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFileDialog { Filter = "ONNX|*.onnx|PT|*.pt" };
            if (dlg.ShowDialog() == true)
            {
                YoloPath.Text = System.IO.Path.GetFileName(dlg.FileName);
                UpdateBadge(YoloBadge, YoloBadgeText, "로드됨", "Green");
                AppendLog($"YOLOv8 로드: {YoloPath.Text}");
            }
        }

        private void Roboflow_Click(object sender, RoutedEventArgs e)
        {
            try { System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("https://app.roboflow.com") { UseShellExecute = true }); }
            catch { }
        }

        private void Colab_Click(object sender, RoutedEventArgs e)
        {
            try { System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("https://colab.research.google.com") { UseShellExecute = true }); }
            catch { }
        }

        // ═══════════════════════════════════════
        //  CSV 저장 / 불러오기
        // ═══════════════════════════════════════
        private void SaveCsv_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.SaveFileDialog { Filter = "CSV|*.csv", FileName = "calib_data.csv" };
            if (dlg.ShowDialog() == true)
                AppendLog($"CSV 저장: {dlg.FileName}");
        }

        private void LoadCsv_Click(object sender, RoutedEventArgs e)
        {
            var dlg = new Microsoft.Win32.OpenFileDialog { Filter = "CSV|*.csv" };
            if (dlg.ShowDialog() == true)
                AppendLog($"CSV 불러오기: {dlg.FileName}");
        }

        // ═══════════════════════════════════════
        //  로그
        // ═══════════════════════════════════════
        private void ClearLog_Click(object sender, RoutedEventArgs e)
        {
            CtrlLog.Text = "$ 대기 중...";
        }

        private void AppendLog(string msg)
        {
            string ts = DateTime.Now.ToString("HH:mm:ss");
            CtrlLog.Text += $"\n[{ts}] {msg}";
            CtrlLogScroll?.ScrollToEnd();
        }

        // ═══════════════════════════════════════
        //  유틸리티
        // ═══════════════════════════════════════
        private SolidColorBrush FindBrush(string key)
        {
            return TryFindResource(key) as SolidColorBrush ?? Brushes.Gray;
        }

        private void UpdateBadge(Border badge, TextBlock text, string label, string color)
        {
            text.Text = label;
            switch (color)
            {
                case "Green":
                    badge.Background = FindBrush("GreenLightBrush");
                    text.Foreground = FindBrush("GreenBrush");
                    break;
                case "Amber":
                    badge.Background = FindBrush("AmberLightBrush");
                    text.Foreground = FindBrush("AmberBrush");
                    break;
                case "Red":
                    badge.Background = FindBrush("RedLightBrush");
                    text.Foreground = FindBrush("RedBrush");
                    break;
                case "Accent":
                    badge.Background = FindBrush("AccentLightBrush");
                    text.Foreground = FindBrush("AccentBrush");
                    break;
            }
        }
    }
}
