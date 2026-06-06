using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace LabSafetyManager
{
    /// <summary>
    /// 통제실 fall_detection.py와 통신하는 클라이언트.
    ///
    /// 포트:
    ///   9998 UDP - 비상/해제 신호 양방향
    ///              통제실→보안실: {"type":"emergency","ts":"..."}
    ///              보안실→통제실: {"type":"clear"}
    ///   9999 TCP - 카메라 영상 스트리밍
    /// </summary>
    public class FallTcpClient
    {
        private readonly string _host;
        private readonly int _tcpPort;
        private readonly int _udpPort;

        private CancellationTokenSource? _udpCts;
        private CancellationTokenSource? _tcpCts;
        private bool _tcpRunning = false;
        private DateTime _cooldownUntil = DateTime.MinValue;

        public event EventHandler<byte[]>? FrameReceived;
        public event EventHandler<string>? EmergencyReceived;
        public event EventHandler<bool>? ConnectionChanged;

        public bool IsTcpRunning => _tcpRunning;

        public FallTcpClient(string host, int tcpPort = 9999, int udpPort = 9998)
        {
            _host = host;
            _tcpPort = tcpPort;
            _udpPort = udpPort;
        }

        // ── UDP 수신 시작 (앱 시작 시) ───────────────────────────
        public void StartUdpListener()
        {
            _udpCts = new CancellationTokenSource();
            _ = Task.Run(() => UdpListenAsync(_udpCts.Token));
        }

        // ── TCP 연결 시작 ────────────────────────────────────────
        public void StartTcp()
        {
            if (_tcpRunning) return;
            _tcpRunning = true;
            _tcpCts = new CancellationTokenSource();
            _ = Task.Run(() => TcpConnectAsync(_host, _tcpCts.Token));
        }

        // ── TCP 연결 종료 ────────────────────────────────────────
        public void StopTcp()
        {
            _tcpCts?.Cancel();
            _tcpRunning = false;
        }

        // ── 완전 종료 (앱 닫을 때) ──────────────────────────────
        public void StopAll()
        {
            _udpCts?.Cancel();
            _tcpCts?.Cancel();
            _tcpRunning = false;
        }

        // ── 쿨다운 설정/해제 ─────────────────────────────────────
        public void SetCooldown(int seconds)
        {
            _cooldownUntil = DateTime.Now.AddSeconds(seconds);
        }

        public void ResetCooldown()
        {
            _cooldownUntil = DateTime.MinValue;
        }

        // ── 보안실 → 통제실 해제 신호 전송 (포트 9998 유니캐스트) ─
        public void SendClearSignal()
        {
            try
            {
                using var sock = new UdpClient();
                var msg = Encoding.UTF8.GetBytes(
                    JsonSerializer.Serialize(new { type = "clear" }));
                sock.Send(msg, msg.Length, _host, _udpPort);
                Console.WriteLine($"[UDP:{_udpPort}] 해제 신호 전송 → {_host}");
            }
            catch (Exception e)
            {
                Console.WriteLine($"[UDP] 해제 신호 전송 실패: {e.Message}");
            }
        }

        // ── UDP 수신 루프 ────────────────────────────────────────
        private async Task UdpListenAsync(CancellationToken token)
        {
            using var udp = new UdpClient();
            udp.Client.SetSocketOption(SocketOptionLevel.Socket,
                SocketOptionName.ReuseAddress, true);
            udp.Client.Bind(new IPEndPoint(IPAddress.Any, _udpPort));

            Console.WriteLine($"[UDP:{_udpPort}] 수신 대기 중");

            while (!token.IsCancellationRequested)
            {
                try
                {
                    var result = await udp.ReceiveAsync(token);
                    var json = Encoding.UTF8.GetString(result.Buffer);

                    using var doc = JsonDocument.Parse(json);
                    var root = doc.RootElement;
                    if (!root.TryGetProperty("type", out var t)) continue;

                    var type = t.GetString();
                    if (type != "emergency") continue;  // clear는 통제실이 처리

                    // 쿨다운 중 무시
                    if (DateTime.Now < _cooldownUntil) continue;

                    var ts = root.TryGetProperty("ts", out var tsEl)
                        ? tsEl.GetString() ?? "" : "";

                    EmergencyReceived?.Invoke(this, ts);

                    if (!_tcpRunning)
                        StartTcp();
                }
                catch (OperationCanceledException) { break; }
                catch { }
            }
        }

        // ── TCP 연결 루프 ────────────────────────────────────────
        private async Task TcpConnectAsync(string host, CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                TcpClient? tcp = null;
                try
                {
                    tcp = new TcpClient();
                    tcp.ReceiveTimeout = 5000;
                    await tcp.ConnectAsync(host, _tcpPort, token);
                    ConnectionChanged?.Invoke(this, true);
                    await ReceiveAsync(tcp.GetStream(), token);
                }
                catch (OperationCanceledException) { break; }
                catch { }
                finally { try { tcp?.Close(); } catch { } }

                if (token.IsCancellationRequested) break;
                ConnectionChanged?.Invoke(this, false);

                try { await Task.Delay(2000, token); }
                catch (OperationCanceledException) { break; }
            }
            _tcpRunning = false;
        }

        // ── 프레임 수신 ─────────────────────────────────────────
        private async Task ReceiveAsync(NetworkStream stream, CancellationToken token)
        {
            var lenBuf = new byte[4];
            while (!token.IsCancellationRequested)
            {
                if (!await ReadExactAsync(stream, lenBuf, 4, token)) return;
                int len = (lenBuf[0] << 24) | (lenBuf[1] << 16) |
                          (lenBuf[2] << 8) | lenBuf[3];

                if (len <= 0 || len > 10 * 1024 * 1024) return;

                var data = new byte[len];
                if (!await ReadExactAsync(stream, data, len, token)) return;

                FrameReceived?.Invoke(this, data);
            }
        }

        private static async Task<bool> ReadExactAsync(
            NetworkStream stream, byte[] buf, int count, CancellationToken token)
        {
            int offset = 0;
            while (offset < count)
            {
                int read = await stream.ReadAsync(buf, offset, count - offset, token);
                if (read == 0) return false;
                offset += read;
            }
            return true;
        }
    }
}