using System;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Threading;
using OpenCvSharp;
using OpenCvSharp.WpfExtensions;

namespace monitoring_wpf.Views
{
    public partial class FaceAuthView : UserControl
    {
        public Action? OnAuthComplete { get; set; }

        private CancellationTokenSource? _cts;
        private readonly DispatcherTimer _authTimer = new();
        private readonly DispatcherTimer _scanTimer  = new();
        private double _scanY = 0;

        public FaceAuthView()
        {
            InitializeComponent();
            Loaded   += (_, _) => OnLoaded();
            Unloaded += (_, _) => StopCamera();
        }

        private void OnLoaded()
        {
            StartScanAnimation();
            StartCamera();

            // 3초 후 인증 완료
            _authTimer.Interval = TimeSpan.FromSeconds(3);
            _authTimer.Tick += (_, _) =>
            {
                _authTimer.Stop();
                ShowAuthComplete();
            };
            _authTimer.Start();
        }

        // ── 스캔 라인 애니메이션 ──────────────────────────────────
        private void StartScanAnimation()
        {
            _scanTimer.Interval = TimeSpan.FromMilliseconds(16);
            _scanTimer.Tick += (_, _) =>
            {
                _scanY += 2.5;
                if (_scanY > 420) _scanY = 0;
                ScanTranslate.Y = _scanY;
            };
            _scanTimer.Start();
        }

        // ── 카메라 캡처 ──────────────────────────────────────────
        private void StartCamera()
        {
            _cts = new CancellationTokenSource();
            var token = _cts.Token;

            Task.Run(async () =>
            {
                VideoCapture? cap = null;
                try
                {
                    cap = new VideoCapture(0, VideoCaptureAPIs.DSHOW);
                    if (!cap.IsOpened())
                    {
                        await Dispatcher.InvokeAsync(() => NoCamPlaceholder.Visibility = Visibility.Visible);
                        return;
                    }

                    using var frame = new Mat();
                    while (!token.IsCancellationRequested)
                    {
                        cap.Read(frame);
                        if (!frame.Empty())
                        {
                            var bs = BitmapSourceConverter.ToBitmapSource(frame);
                            bs.Freeze();
                            await Dispatcher.InvokeAsync(() => CameraImage.Source = bs);
                        }
                        await Task.Delay(30, token);
                    }
                }
                catch (OperationCanceledException) { }
                catch
                {
                    await Dispatcher.InvokeAsync(() => NoCamPlaceholder.Visibility = Visibility.Visible);
                }
                finally
                {
                    cap?.Dispose();
                }
            }, token);
        }

        public void StopCamera()
        {
            _authTimer.Stop();
            _scanTimer.Stop();
            _cts?.Cancel();
        }

        // ── 인증 완료 연출 ────────────────────────────────────────
        private void ShowAuthComplete()
        {
            // 브라켓 색 → 밝은 초록으로 강조
            foreach (var name in new[] { "BL_V1", "BL_H1", "BR_V1", "BR_H1",
                                         "BL_V2", "BL_H2", "BR_V2", "BR_H2" })
            {
                if (FindName(name) is System.Windows.Shapes.Line line)
                    line.Stroke = new SolidColorBrush(Color.FromRgb(0x16, 0xA3, 0x4A));
            }

            AuthBadge.Visibility = Visibility.Visible;
            AuthBadgeText.Text   = "김수영 연구원 인증완료";
            AuthLine1.Text       = "인증이 완료되었습니다";
            AuthLine2.Text       = "잠시 후 이동합니다...";

            // 스캔 라인 정지
            _scanTimer.Stop();

            // 1.5초 후 이동
            var nav = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1.5) };
            nav.Tick += (_, _) => { nav.Stop(); StopCamera(); OnAuthComplete?.Invoke(); };
            nav.Start();
        }
    }
}
