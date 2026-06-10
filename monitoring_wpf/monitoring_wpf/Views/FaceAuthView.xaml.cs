using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Threading;
using OpenCvSharp;
using OpenCvSharp.WpfExtensions;

namespace monitoring_wpf.Views
{
    public partial class FaceAuthView : UserControl
    {
        public Action? OnAuthComplete { get; set; }

        private CancellationTokenSource? _cts;
        private readonly DispatcherTimer _scanTimer = new();
        private readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(5) };
        private const string FlaskUrl = "http://127.0.0.1:5000/api/face/login";

        private double _scanY = 0;
        private bool _isAuthenticating = false;
        private bool _isFailed = false;

        public FaceAuthView()
        {
            InitializeComponent();
            Loaded += (_, _) => OnLoaded();
            Unloaded += (_, _) => StopCamera();
            IsVisibleChanged += (_, _) =>
            {
                if (IsVisible)
                {
                    ResetView();
                    StartScanAnimation();
                    StartCamera();
                }
                else
                {
                    StopCamera();
                }
            };
        }

        /// <summary>
        /// UI 상태 초기화 — 로그아웃 후 다시 돌아왔을 때 이전 인증 결과 제거
        /// </summary>
        private void ResetView()
        {
            _isAuthenticating = false;
            _isFailed = false;
            _scanY = 0;

            AuthBadge.Visibility = Visibility.Collapsed;
            ConfidencePanel.Visibility = Visibility.Collapsed;
            NoCamPlaceholder.Visibility = Visibility.Collapsed;
            AuthLine1.Text = "얼굴을 카메라에 맞춰주세요";
            AuthLine2.Text = "";

            // 코너 라인 색상 원래대로 (초록)
            foreach (var n in new[] { "BL_V1", "BL_H1", "BR_V1", "BR_H1", "BL_V2", "BL_H2", "BR_V2", "BR_H2" })
                if (FindName(n) is System.Windows.Shapes.Line l)
                    l.Stroke = new SolidColorBrush(Color.FromRgb(0x22, 0xC5, 0x5E));

            // ◀ 테스트용 임시 자동 인증 (나중에 삭제!)
            var skip = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
            skip.Tick += (_, _) => { skip.Stop(); ShowAuthComplete(1, "강은비", "연구원", 99.9); };
            skip.Start();
        }

        private void OnLoaded()
        {
            // IsVisibleChanged 에서 처리하므로 여기서는 아무것도 안 함
            // (Loaded + IsVisibleChanged 동시 발생 시 중복 방지)
        }

        // 스캔 라인 애니메이션
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

        // 카메라 캡처 + 인증
        private void StartCamera()
        {
            _cts = new CancellationTokenSource();
            var token = _cts.Token;

            Task.Run(async () =>
            {
                VideoCapture? cap = null;
                try
                {
                    cap = new VideoCapture(2, VideoCaptureAPIs.DSHOW);
                    if (!cap.IsOpened())
                    {
                        await Dispatcher.InvokeAsync(() =>
                            NoCamPlaceholder.Visibility = Visibility.Visible);
                        return;
                    }

                    using var frame = new Mat();
                    int frameCount = 0;

                    while (!token.IsCancellationRequested)
                    {
                        cap.Read(frame);
                        if (frame.Empty()) { await Task.Delay(30, token); continue; }

                        var bs = BitmapSourceConverter.ToBitmapSource(frame);
                        bs.Freeze();
                        await Dispatcher.InvokeAsync(() => CameraImage.Source = bs);

                        frameCount++;
                        if (frameCount % 15 == 0 && !_isAuthenticating && !_isFailed)
                        {
                            // JPEG 품질 95%로 인코딩 (기본값보다 훨씬 선명)
                            var encParams = new ImageEncodingParam(ImwriteFlags.JpegQuality, 95);
                            var jpegBytes = frame.ToBytes(".jpg", new[] { encParams });
                            _ = TryAuthenticateAsync(jpegBytes, token);
                        }

                        await Task.Delay(30, token);
                    }
                }
                catch (OperationCanceledException) { }
                catch
                {
                    await Dispatcher.InvokeAsync(() =>
                        NoCamPlaceholder.Visibility = Visibility.Visible);
                }
                finally { cap?.Dispose(); }
            }, token);
        }

        // Flask 인증 요청
        private async Task TryAuthenticateAsync(byte[] jpegBytes, CancellationToken token)
        {
            _isAuthenticating = true;
            try
            {
                var content = new ByteArrayContent(jpegBytes);
                content.Headers.ContentType =
                    new System.Net.Http.Headers.MediaTypeHeaderValue("image/jpeg");

                var response = await _http.PostAsync(FlaskUrl, content, token);
                if (!response.IsSuccessStatusCode) return;

                var json = await response.Content.ReadAsStringAsync(token);
                var result = JsonSerializer.Deserialize<AuthResult>(json);

                await Dispatcher.InvokeAsync(() =>
                {
                    if (result?.Ok == true)
                        ShowAuthComplete(result.Id, result.Name, result.Role, result.Confidence);
                    else if (result?.Retry == true)
                        AuthLine1.Text = string.IsNullOrEmpty(result.Reason)
                            ? "얼굴 인식 중..."
                            : result.Reason;
                    else
                        ShowAuthFailed();
                });
            }
            catch { }
            finally { _isAuthenticating = false; }
        }

        // 인증 실패
        private void ShowAuthFailed()
        {
            _isFailed = true;
            _scanTimer.Stop();

            foreach (var n in new[] { "BL_V1", "BL_H1", "BR_V1", "BR_H1", "BL_V2", "BL_H2", "BR_V2", "BR_H2" })
                if (FindName(n) is System.Windows.Shapes.Line l)
                    l.Stroke = new SolidColorBrush(Color.FromRgb(0xEF, 0x44, 0x44));

            ConfidencePanel.Visibility = Visibility.Visible;
            ConfidenceStatus.Text = "인증 실패";
            ConfidencePercent.Text = "✗";
            ConfidencePercent.Foreground = new SolidColorBrush(Color.FromRgb(0xEF, 0x44, 0x44));
            ConfidenceFill.Width = 0;

            AuthLine1.Text = "인증에 실패하였습니다";
            AuthLine2.Text = "관리자에게 문의하세요";
            AuthLine2.Foreground = new SolidColorBrush(Color.FromRgb(0xEF, 0x44, 0x44));
        }

        public void StopCamera()
        {
            _scanTimer.Stop();
            _cts?.Cancel();
        }

        // 인증 성공
        private void ShowAuthComplete(int id, string name, string role, double confidence)
        {
            if (AuthBadge.Visibility == Visibility.Visible) return;

            // 인증된 연구원 이름 저장
            MainWindow.AuthName = name;
            MainWindow.AuthRole = role;
            MainWindow.AuthId = id;

            ConfidencePanel.Visibility = Visibility.Visible;
            ConfidenceStatus.Text = "인증 성공!";
            ConfidencePercent.Text = $"{confidence}%";
            ConfidencePercent.Foreground = new SolidColorBrush(Color.FromRgb(0x22, 0xC5, 0x5E));
            ConfidenceFill.Width = confidence / 100.0 * 200;
            ConfidenceFill.Fill = new SolidColorBrush(Color.FromRgb(0x22, 0xC5, 0x5E));

            foreach (var n in new[] { "BL_V1", "BL_H1", "BR_V1", "BR_H1", "BL_V2", "BL_H2", "BR_V2", "BR_H2" })
                if (FindName(n) is System.Windows.Shapes.Line l)
                    l.Stroke = new SolidColorBrush(Color.FromRgb(0x16, 0xA3, 0x4A));

            AuthBadge.Visibility = Visibility.Visible;
            AuthBadgeText.Text = $"{name} {role} 인증완료";
            AuthLine1.Text = $"신뢰도 {confidence}% 로 인증이 완료되었습니다";
            AuthLine2.Text = "잠시 후 이동합니다...";
            AuthLine2.Foreground = new SolidColorBrush(Color.FromRgb(0x22, 0xC5, 0x5E));

            _scanTimer.Stop();

            var nav = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1.5) };
            nav.Tick += (_, _) => { nav.Stop(); StopCamera(); OnAuthComplete?.Invoke(); };
            nav.Start();
        }

        private class AuthResult
        {
            [System.Text.Json.Serialization.JsonPropertyName("ok")]
            public bool Ok { get; set; }
            [System.Text.Json.Serialization.JsonPropertyName("name")]
            public string Name { get; set; } = "";
            [System.Text.Json.Serialization.JsonPropertyName("id")]
            public int Id { get; set; }
            [System.Text.Json.Serialization.JsonPropertyName("role")]
            public string Role { get; set; } = "";
            [System.Text.Json.Serialization.JsonPropertyName("confidence")]
            public double Confidence { get; set; }
            [System.Text.Json.Serialization.JsonPropertyName("reason")]
            public string Reason { get; set; } = "";
            [System.Text.Json.Serialization.JsonPropertyName("retry")]
            public bool Retry { get; set; }
        }
    }
}