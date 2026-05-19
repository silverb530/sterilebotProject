using System;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Controls;
using System.Windows;
using OpenCvSharp;
using OpenCvSharp.WpfExtensions;

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

        public void Stop() => _cts?.Cancel();

        private void ShowNoSignal(bool show)
        {
            NoSignal.Visibility  = show ? System.Windows.Visibility.Visible : System.Windows.Visibility.Collapsed;
            FeedImage.Visibility = show ? System.Windows.Visibility.Collapsed : System.Windows.Visibility.Visible;
        }
    }
}
