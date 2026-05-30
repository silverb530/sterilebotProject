using OpenCvSharp;
using OpenCvSharp.WpfExtensions;
using System;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Imaging;

namespace monitoring_wpf.Views
{
    public partial class CameraFeedControl : UserControl
    {
        private CancellationTokenSource? _cts;
        private int _cameraIndex = 0;

        public CameraFeedControl()
        {
            InitializeComponent();
        }

        public void Start(int cameraIndex = 1, string noSignalLabel = "카메라 신호 없음")
        {
            _cameraIndex = cameraIndex;
            NoSignalText.Text = noSignalLabel;
            Stop();

            _cts = new CancellationTokenSource();
            var token = _cts.Token;

            Task.Run(async () =>
            {
                VideoCapture? cap = null;
                try
                {
                    cap = new VideoCapture(_cameraIndex, VideoCaptureAPIs.DSHOW);
                    if (!cap.IsOpened())
                    {
                        await Dispatcher.InvokeAsync(() => ShowNoSignal(true));
                        return;
                    }
                    await Dispatcher.InvokeAsync(() => ShowNoSignal(false));

                    using var frame = new Mat();
                    while (!token.IsCancellationRequested)
                    {
                        cap.Read(frame);
                        if (!frame.Empty())
                        {
                            var bs = BitmapSourceConverter.ToBitmapSource(frame);
                            bs.Freeze();
                            await Dispatcher.InvokeAsync(() => FeedImage.Source = bs);
                        }
                        await Task.Delay(33, token);
                    }
                }
                catch (OperationCanceledException) { }
                catch
                {
                    await Dispatcher.InvokeAsync(() => ShowNoSignal(true));
                }
                finally
                {
                    cap?.Dispose();
                }
            }, token);
        }

        // ═══ MJPEG over HTTP 수신 (Zone_tracker 스트림용) ═══
        public void StartMjpeg(string url, string noSignalLabel = "스트림 대기 중")
        {
            NoSignalText.Text = noSignalLabel;
            Stop();
            _cts = new CancellationTokenSource();
            var token = _cts.Token;

            Task.Run(async () =>
            {
                while (!token.IsCancellationRequested)
                {
                    try { await ReadMjpegStream(url, token); }
                    catch (OperationCanceledException) { return; }
                    catch
                    {
                        await Dispatcher.InvokeAsync(() => ShowNoSignal(true));
                        try { await Task.Delay(1500, token); } catch { return; }
                    }
                }
            }, token);
        }

        private async Task ReadMjpegStream(string url, CancellationToken token)
        {
            using var http = new HttpClient { Timeout = Timeout.InfiniteTimeSpan };
            using var resp = await http.GetAsync(url, HttpCompletionOption.ResponseHeadersRead, token);
            resp.EnsureSuccessStatusCode();
            await Dispatcher.InvokeAsync(() => ShowNoSignal(false));

            using var stream = await resp.Content.ReadAsStreamAsync(token);
            var buffer = new System.Collections.Generic.List<byte>(1 << 18);
            int prev = -1;
            bool inJpeg = false;

            while (!token.IsCancellationRequested)
            {
                int b = stream.ReadByte();
                if (b < 0) break;
                if (!inJpeg)
                {
                    if (prev == 0xFF && b == 0xD8)
                    {
                        inJpeg = true;
                        buffer.Clear();
                        buffer.Add(0xFF); buffer.Add(0xD8);
                    }
                }
                else
                {
                    buffer.Add((byte)b);
                    if (prev == 0xFF && b == 0xD9)
                    {
                        RenderJpeg(buffer.ToArray());
                        inJpeg = false;
                    }
                }
                prev = b;
            }
        }

        private void RenderJpeg(byte[] jpegBytes)
        {
            try
            {
                var bmp = new BitmapImage();
                using (var ms = new MemoryStream(jpegBytes))
                {
                    bmp.BeginInit();
                    bmp.CacheOption = BitmapCacheOption.OnLoad;
                    bmp.StreamSource = ms;
                    bmp.EndInit();
                }
                bmp.Freeze();
                Dispatcher.InvokeAsync(() => FeedImage.Source = bmp);
            }
            catch { }
        }

        public void Stop() => _cts?.Cancel();

        private void ShowNoSignal(bool show)
        {
            NoSignal.Visibility = show ? System.Windows.Visibility.Visible : System.Windows.Visibility.Collapsed;
            FeedImage.Visibility = show ? System.Windows.Visibility.Collapsed : System.Windows.Visibility.Visible;
        }
    }
}