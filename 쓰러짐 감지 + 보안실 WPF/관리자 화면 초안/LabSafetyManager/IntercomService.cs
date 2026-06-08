using System;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using System.Threading.Tasks;
using NAudio.Wave;

namespace LabSafetyManager
{
    /// <summary>
    /// 양방향 인터컴 서비스
    /// 보안실 마이크 → UDP 10000 → Pi 스피커
    /// Pi 마이크    → UDP 10001 → 보안실 스피커
    /// </summary>
    public class IntercomService : IDisposable
    {
        private const int VOICE_PORT = 10000;  // 양방향 공용 포트
        private const int RATE = 16000;
        private const int CHANNELS = 1;
        private const int BLOCK_MS = 40;

        private readonly string _piIp;

        private CancellationTokenSource? _cts;
        private WaveInEvent? _mic;
        private WaveOutEvent? _speaker;
        private BufferedWaveProvider? _buffer;
        private UdpClient? _sendSock;
        private UdpClient? _recvSock;

        public bool IsRunning { get; private set; }

        public IntercomService(string piIp)
        {
            _piIp = piIp;
        }

        /// <summary>비상 시작 시 호출 — 인터컴 시작</summary>
        public void Start()
        {
            if (IsRunning) return;
            IsRunning = true;
            _cts = new CancellationTokenSource();

            StartMic();
            StartSpeaker();
            _ = Task.Run(() => ReceiveLoopAsync(_cts.Token));
        }

        /// <summary>비상 해제 시 호출 — 인터컴 종료</summary>
        public void Stop()
        {
            if (!IsRunning) return;
            IsRunning = false;
            _cts?.Cancel();

            try { _mic?.StopRecording(); } catch { }
            try { _speaker?.Stop(); } catch { }
            try { _sendSock?.Close(); } catch { }
            try { _recvSock?.Close(); } catch { }

            _mic?.Dispose(); _mic = null;
            _speaker?.Dispose(); _speaker = null;
            _sendSock?.Dispose(); _sendSock = null;
            _recvSock?.Dispose(); _recvSock = null;
            _buffer = null;
        }

        // ── 마이크 캡처 → Pi로 송신 ──────────────────────────
        private void StartMic()
        {
            _sendSock = new UdpClient();

            _mic = new WaveInEvent
            {
                WaveFormat = new WaveFormat(RATE, 16, CHANNELS),
                BufferMilliseconds = BLOCK_MS,
            };

            _mic.DataAvailable += (_, e) =>
            {
                if (!IsRunning) return;
                try
                {
                    var buf = new byte[e.BytesRecorded];
                    Array.Copy(e.Buffer, buf, e.BytesRecorded);
                    _sendSock?.Send(buf, buf.Length, _piIp, VOICE_PORT);
                }
                catch { }
            };

            _mic.StartRecording();
        }

        // ── Pi로부터 수신 → 보안실 스피커 재생 ──────────────
        private void StartSpeaker()
        {
            var fmt = new WaveFormat(RATE, 16, CHANNELS);
            _buffer = new BufferedWaveProvider(fmt)
            {
                BufferDuration = TimeSpan.FromSeconds(1),
                DiscardOnBufferOverflow = true,
            };

            _speaker = new WaveOutEvent();
            _speaker.Init(_buffer);
            _speaker.Play();
        }

        private async Task ReceiveLoopAsync(CancellationToken token)
        {
            _recvSock = new UdpClient();
            _recvSock.Client.SetSocketOption(SocketOptionLevel.Socket,
                SocketOptionName.ReuseAddress, true);
            _recvSock.Client.Bind(new IPEndPoint(IPAddress.Any, VOICE_PORT));

            System.Diagnostics.Debug.WriteLine($"[인터컴] UDP {VOICE_PORT} 수신 대기");

            while (!token.IsCancellationRequested)
            {
                try
                {
                    var result = await _recvSock.ReceiveAsync(token);
                    _buffer?.AddSamples(result.Buffer, 0, result.Buffer.Length);
                }
                catch (OperationCanceledException) { break; }
                catch { }
            }
        }

        public void Dispose() => Stop();
    }
}