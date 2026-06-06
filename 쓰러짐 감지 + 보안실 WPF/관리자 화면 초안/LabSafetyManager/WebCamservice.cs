using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using OpenCvSharp;

namespace LabSafetyManager
{
    /// <summary>
    /// 로컬 웹캠을 OpenCvSharp4로 열어서 JPEG 프레임을 이벤트로 내보낸다.
    /// 런타임에 카메라 인덱스를 바꿔가며 다른 카메라(USB 웹캠 등)로 전환할 수 있다.
    /// </summary>
    public class WebcamService
    {
        private CancellationTokenSource? _cts;
        private Task? _loopTask;

        public int CameraIndex { get; private set; } = 0;
        public int FrameWidth { get; set; } = 640;
        public int FrameHeight { get; set; } = 480;
        public int JpegQuality { get; set; } = 75;

        public event EventHandler<byte[]>? FrameReceived;
        public event EventHandler<string>? StatusChanged;

        public bool IsRunning => _loopTask is { IsCompleted: false };

        /// <summary>지정한 인덱스로 캡처 시작. 인덱스 생략 시 현재 인덱스 유지.</summary>
        public void Start(int? cameraIndex = null)
        {
            Stop();
            if (cameraIndex.HasValue) CameraIndex = cameraIndex.Value;

            _cts = new CancellationTokenSource();
            var token = _cts.Token;
            var idx = CameraIndex;
            _loopTask = Task.Run(() => CaptureLoop(idx, token), token);
        }

        public void Stop()
        {
            try
            {
                _cts?.Cancel();
                _loopTask?.Wait(1500);
            }
            catch { /* 종료 중 예외 무시 */ }
            finally
            {
                _cts?.Dispose();
                _cts = null;
                _loopTask = null;
            }
        }

        /// <summary>
        /// 사용 가능한 카메라 인덱스 목록을 비동기로 조회한다.
        /// 각 인덱스마다 잠시 열어 프레임이 읽히는지 확인하므로 2~5초 걸린다.
        /// 호출하기 전에 반드시 현재 캡처를 Stop()해야 한다(같은 카메라를 두 번 열 수 없음).
        /// </summary>
        public static Task<List<int>> EnumerateCamerasAsync(int maxIndex = 5)
        {
            return Task.Run(() =>
            {
                var found = new List<int>();
                for (int i = 0; i <= maxIndex; i++)
                {
                    VideoCapture? cap = null;
                    try
                    {
                        cap = new VideoCapture(i, VideoCaptureAPIs.DSHOW);
                        if (!cap.IsOpened()) continue;

                        using var mat = new Mat();
                        // 첫 프레임이 한 박자 늦게 오는 카메라도 있어 몇 번 시도
                        bool ok = false;
                        for (int retry = 0; retry < 5; retry++)
                        {
                            if (cap.Read(mat) && !mat.Empty()) { ok = true; break; }
                            Thread.Sleep(100);
                        }
                        if (ok) found.Add(i);
                    }
                    catch { /* 해당 인덱스는 사용 불가 */ }
                    finally
                    {
                        try { cap?.Release(); cap?.Dispose(); } catch { }
                    }
                }
                return found;
            });
        }

        private void CaptureLoop(int idx, CancellationToken token)
        {
            VideoCapture? cap = null;
            try
            {
                StatusChanged?.Invoke(this, "starting");

                cap = new VideoCapture(idx, VideoCaptureAPIs.DSHOW);
                if (!cap.IsOpened())
                {
                    cap.Dispose();
                    cap = new VideoCapture(idx);
                }
                if (!cap.IsOpened())
                {
                    StatusChanged?.Invoke(this,
                        $"error: 카메라 {idx}를 열 수 없습니다 (다른 앱이 사용 중이거나 권한이 없습니다)");
                    return;
                }

                cap.Set(VideoCaptureProperties.FrameWidth, FrameWidth);
                cap.Set(VideoCaptureProperties.FrameHeight, FrameHeight);
                cap.Set(VideoCaptureProperties.BufferSize, 1);

                StatusChanged?.Invoke(this, "running");

                using var mat = new Mat();
                var encodeParams = new ImageEncodingParam(ImwriteFlags.JpegQuality, JpegQuality);

                int emptyStreak = 0;
                while (!token.IsCancellationRequested)
                {
                    if (!cap.Read(mat) || mat.Empty())
                    {
                        if (++emptyStreak > 30)
                        {
                            StatusChanged?.Invoke(this, "error: 카메라 신호 없음");
                            break;
                        }
                        Thread.Sleep(50);
                        continue;
                    }
                    emptyStreak = 0;

                    Cv2.ImEncode(".jpg", mat, out var jpg, encodeParams);
                    FrameReceived?.Invoke(this, jpg);

                    Thread.Sleep(33); // ~30 fps 상한
                }
            }
            catch (Exception ex)
            {
                StatusChanged?.Invoke(this, $"error: {ex.Message}");
            }
            finally
            {
                try { cap?.Release(); } catch { }
                try { cap?.Dispose(); } catch { }
                StatusChanged?.Invoke(this, "stopped");
            }
        }
    }

    /// <summary>ComboBox에 표시할 카메라 항목.</summary>
    public record CameraOption(int Index, string Name)
    {
        public override string ToString() => Name;
    }
}
