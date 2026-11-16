// SmartVoiceEditor-Online-Setup.exe: a small installer that takes everything from the internet:
// the newest program release (GitHub), Python 3.12 (python.org NuGet package, checksum pinned),
// the Python packages (pip; CUDA libraries when an NVIDIA driver is present) and, if chosen, the models.
// No administrator rights; nothing is installed system-wide.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Net;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows.Forms;

namespace SmartVoice
{
    sealed class OnlineSetupForm : Form
    {
        const string Repo = "Otajon2300/smart-voice-editor";
        const string PythonUrl = "https://api.nuget.org/v3-flatcontainer/python/3.12.10/python.3.12.10.nupkg";
        const string PythonSha = "0eb85c2dfccccf1b17352de4c397f69194035b7d37149eacc16f1147d93de3b8";
        readonly TextBox folder = new TextBox();
        readonly Button browse = new Button(), install = new Button();
        readonly CheckBox uzbek = new CheckBox(), russian = new CheckBox();
        readonly ProgressBar bar = new ProgressBar();
        readonly Label status = new Label();
        readonly TextBox log = new TextBox();
        bool working, finished;

        OnlineSetupForm()
        {
            Text = "Smart Voice Editor — onlayn o'rnatish (otashDEV)";
            ClientSize = new Size(600, 430);
            FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen;
            Font = new Font("Segoe UI", 9.5f);
            Label head = new Label { Text = "Smart Voice Editor — Premiere Pro uchun ovoz tozalash paneli", Location = new Point(16, 14), AutoSize = true, Font = new Font(Font, FontStyle.Bold) };
            Label note = new Label { Text = "Hammasi internetdan yuklanadi (Python, kutubxonalar, modellar). Administrator huquqi kerak emas.", Location = new Point(16, 38), Size = new Size(570, 20) };
            Label where = new Label { Text = "O'rnatish papkasi:", Location = new Point(16, 66), AutoSize = true };
            folder.Location = new Point(16, 88); folder.Width = 470;
            folder.Text = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "SmartVoiceEditor");
            browse.Text = "Tanlash…"; browse.Location = new Point(494, 86); browse.Width = 90;
            browse.Click += delegate
            {
                using (FolderBrowserDialog d = new FolderBrowserDialog())
                    if (d.ShowDialog(this) == DialogResult.OK) folder.Text = Path.Combine(d.SelectedPath, "SmartVoiceEditor");
            };
            uzbek.Text = "O'zbekcha modelni hozir yuklash (3.1 GB)"; uzbek.Checked = true; uzbek.Location = new Point(16, 120); uzbek.AutoSize = true;
            russian.Text = "Ruscha va inglizcha modelni hozir yuklash (1.5 GB)"; russian.Checked = true; russian.Location = new Point(16, 144); russian.AutoSize = true;
            Label later = new Label { Text = "Belgilanmagan model birinchi tahlilda o'zi yuklanadi.", Location = new Point(34, 166), AutoSize = true, ForeColor = Color.DimGray };
            bar.Location = new Point(16, 196); bar.Width = 568; bar.Maximum = 1000;
            status.Location = new Point(16, 224); status.Size = new Size(568, 20);
            status.Text = "Premiere Pro'ni yoping va «O'rnatish» tugmasini bosing.";
            log.Location = new Point(16, 248); log.Size = new Size(568, 130); log.Multiline = true; log.ReadOnly = true; log.ScrollBars = ScrollBars.Vertical;
            log.Font = new Font("Consolas", 8.5f);
            install.Text = "O'rnatish"; install.Location = new Point(464, 388); install.Width = 120; install.Height = 30;
            install.Click += delegate { if (finished) Close(); else Start(); };
            Controls.AddRange(new Control[] { head, note, where, folder, browse, uzbek, russian, later, bar, status, log, install });
            FormClosing += delegate(object s, FormClosingEventArgs e) { if (working) e.Cancel = true; };
        }

        void Report(string text, int progress)
        {
            if (silentLog != null) { if (text != null) Log("» " + text); return; }
            if (InvokeRequired) { BeginInvoke(new Action<string, int>(Report), text, progress); return; }
            if (text != null) { status.Text = text.Length > 110 ? text.Substring(0, 110) + "…" : text; }
            if (progress >= 0) bar.Value = Math.Max(0, Math.Min(1000, progress));
        }

        void Log(string line)
        {
            if (silentLog != null) { lock (this) File.AppendAllText(silentLog, DateTime.Now.ToString("HH:mm:ss ") + line + "\r\n", Encoding.UTF8); return; }
            if (InvokeRequired) { BeginInvoke(new Action<string>(Log), line); return; }
            if (log.TextLength > 60000) log.Text = log.Text.Substring(30000);
            log.AppendText(line + "\r\n");
        }

        void Done(bool ok, string text)
        {
            if (silentLog != null) { finished = ok; Log(text); return; }
            if (InvokeRequired) { BeginInvoke(new Action<bool, string>(Done), ok, text); return; }
            working = false; install.Enabled = true;
            if (ok) { finished = true; install.Text = "Yopish"; bar.Value = 1000; status.Text = "Tayyor."; }
            else { status.Text = "Xato. Qayta urinib ko'rish mumkin — yuklanganlar qayta yuklanmaydi."; folder.Enabled = browse.Enabled = uzbek.Enabled = russian.Enabled = true; }
            Log(text);
            MessageBox.Show(this, text, Text, MessageBoxButtons.OK, ok ? MessageBoxIcon.Information : MessageBoxIcon.Error);
        }

        void Start()
        {
            if (working) return;
            string target = folder.Text.Trim();
            if (target.Length < 4 || !Path.IsPathRooted(target)) { MessageBox.Show(this, "Papka yo'lini to'liq kiriting."); return; }
            working = true; install.Enabled = folder.Enabled = browse.Enabled = uzbek.Enabled = russian.Enabled = false;
            bool uz = uzbek.Checked, ru = russian.Checked;
            Thread worker = new Thread(delegate()
            {
                try { Run(Path.GetFullPath(target), uz, ru); }
                catch (Exception e) { Done(false, "O'rnatishda xato: " + e.Message); }
            });
            worker.IsBackground = true; worker.Start();
        }

        // ---------------------------------------------------------------- downloads
        static string Hex(byte[] hash) { StringBuilder s = new StringBuilder(); foreach (byte b in hash) s.Append(b.ToString("x2")); return s.ToString(); }

        static string FileSha(string path)
        {
            using (SHA256 sha = SHA256.Create()) using (FileStream f = File.OpenRead(path)) return Hex(sha.ComputeHash(f));
        }

        // .NET first; Windows' own curl.exe when the .NET connection fails (old TLS settings, proxies).
        void Download(string url, string path, int from, int to)
        {
            string draft = path + ".partial";
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(url);
                request.UserAgent = "SmartVoiceEditor-installer";
                request.Timeout = 60000; request.ReadWriteTimeout = 120000;
                using (WebResponse response = request.GetResponse())
                using (Stream input = response.GetResponseStream())
                using (FileStream output = File.Create(draft))
                {
                    long total = response.ContentLength, done = 0;
                    byte[] buffer = new byte[1 << 16]; int n;
                    while ((n = input.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        output.Write(buffer, 0, n); done += n;
                        if (total > 0) Report(null, from + (int)((to - from) * done / total));
                    }
                }
            }
            catch (Exception first)
            {
                Log("  .NET bilan yuklanmadi (" + first.Message + "), curl bilan urinilmoqda…");
                string curl = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), "curl.exe");
                if (!File.Exists(curl)) throw new Exception("Yuklab bo'lmadi: " + first.Message);
                if (Execute(curl, "-fsSL --retry 3 -A SmartVoiceEditor-installer -o \"" + draft + "\" \"" + url + "\"", null, null) != 0)
                    throw new Exception("Yuklab bo'lmadi: " + url);
            }
            if (File.Exists(path)) File.Delete(path);
            File.Move(draft, path);
            Report(null, to);
        }

        string ReadText(string url, string path)
        {
            Download(url, path, -1, -1);
            return File.ReadAllText(path, Encoding.UTF8);
        }

        // ---------------------------------------------------------------- processes
        int Execute(string file, string arguments, string directory, string[] env)
        {
            ProcessStartInfo info = new ProcessStartInfo(file, arguments);
            info.UseShellExecute = false; info.CreateNoWindow = true;
            info.RedirectStandardOutput = true; info.RedirectStandardError = true;
            info.StandardOutputEncoding = Encoding.UTF8; info.StandardErrorEncoding = Encoding.UTF8;
            if (directory != null) info.WorkingDirectory = directory;
            info.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            info.EnvironmentVariables["PYTHONUTF8"] = "1";
            info.EnvironmentVariables["PIP_DISABLE_PIP_VERSION_CHECK"] = "1";
            if (env != null) for (int i = 0; i + 1 < env.Length; i += 2) info.EnvironmentVariables[env[i]] = env[i + 1];
            using (Process p = new Process())
            {
                p.StartInfo = info;
                p.OutputDataReceived += delegate(object s, DataReceivedEventArgs e) { if (!string.IsNullOrEmpty(e.Data)) { Log(e.Data); Report(e.Data.Trim(), -1); } };
                p.ErrorDataReceived += delegate(object s, DataReceivedEventArgs e) { if (!string.IsNullOrEmpty(e.Data)) Log(e.Data); };
                p.Start(); p.BeginOutputReadLine(); p.BeginErrorReadLine();
                p.WaitForExit();
                return p.ExitCode;
            }
        }

        static void StopBackend(string target)
        {
            try
            {
                Match m = Regex.Match(File.ReadAllText(Path.Combine(target, ".runtime.json")), "\"pid\"\\s*:\\s*(\\d+)");
                if (!m.Success) return;
                Process p = Process.GetProcessById(int.Parse(m.Groups[1].Value));
                if (p.MainModule.FileName.StartsWith(target, StringComparison.OrdinalIgnoreCase)) { p.Kill(); p.WaitForExit(5000); }
            }
            catch (Exception) { }
        }

        // Extracts the entries under `prefix` into `target`, replacing what is there.
        static void Extract(string zipPath, string prefix, string target)
        {
            string root = target.TrimEnd('\\') + "\\";
            using (ZipArchive zip = ZipFile.OpenRead(zipPath))
                foreach (ZipArchiveEntry e in zip.Entries)
                {
                    string name = e.FullName.Replace('\\', '/');
                    if (!name.StartsWith(prefix) || name.EndsWith("/")) continue;
                    string path = Path.GetFullPath(Path.Combine(target, Uri.UnescapeDataString(name.Substring(prefix.Length)).Replace('/', '\\')));
                    if (!path.StartsWith(root, StringComparison.OrdinalIgnoreCase)) throw new IOException("Paket buzilgan: " + name);
                    Directory.CreateDirectory(Path.GetDirectoryName(path));
                    e.ExtractToFile(path, true);
                }
        }

        static bool HasNvidia()
        {
            string system = Environment.GetFolderPath(Environment.SpecialFolder.System);
            return File.Exists(Path.Combine(system, "nvcuda.dll"));   // installed with every NVIDIA display driver
        }

        // ---------------------------------------------------------------- steps
        void Run(string target, bool uz, bool ru)
        {
            // TLS 1.2 (and 1.3 where .NET knows it): GitHub refuses older protocols.
            ServicePointManager.SecurityProtocol |= (SecurityProtocolType)3072;
            try { ServicePointManager.SecurityProtocol |= (SecurityProtocolType)12288; } catch (Exception) { }
            string drive = Path.GetPathRoot(target);
            long need = (3L << 30) + (uz ? 3200L << 20 : 0) + (ru ? 1600L << 20 : 0);
            long free = new DriveInfo(drive).AvailableFreeSpace;
            if (free < need) throw new IOException(string.Format("{0} diskda joy yetmaydi: kerak ~{1:0.0} GB, bo'sh {2:0.0} GB.", drive, need / 1073741824.0, free / 1073741824.0));
            Directory.CreateDirectory(target);
            string temp = Path.Combine(target, ".update");
            Directory.CreateDirectory(temp);
            StopBackend(target);

            // 1. Program: the newest release, checked against its SHA256.
            Report("Eng yangi versiya aniqlanmoqda (GitHub)…", 10);
            string release = ReadText("https://api.github.com/repos/" + Repo + "/releases/latest", Path.Combine(temp, "release.json"));
            Match tag = Regex.Match(release, "\"tag_name\"\\s*:\\s*\"v?([\\d.]+)\"");
            if (!tag.Success) throw new Exception("GitHub'dan versiya ma'lumoti kelmadi.");
            string version = tag.Groups[1].Value, zipName = "SmartVoiceEditor-" + version + ".zip", shaName = "SmartVoiceEditor-" + version + ".sha256";
            Match zipUrl = Regex.Match(release, "\"browser_download_url\"\\s*:\\s*\"([^\"]*/" + Regex.Escape(zipName) + ")\"");
            Match shaUrl = Regex.Match(release, "\"browser_download_url\"\\s*:\\s*\"([^\"]*/" + Regex.Escape(shaName) + ")\"");
            if (!zipUrl.Success || !shaUrl.Success) throw new Exception("Relizda dastur paketi topilmadi.");
            Log("Versiya: " + version);
            string zipPath = Path.Combine(temp, zipName);
            Download(zipUrl.Groups[1].Value, zipPath, 10, 40);
            string expected = ReadText(shaUrl.Groups[1].Value, Path.Combine(temp, shaName)).Trim().Split(' ', '\t')[0].ToLowerInvariant();
            if (expected != FileSha(zipPath)) throw new Exception("Dastur paketi buzilgan (SHA256 mos emas).");
            Report("Dastur fayllari yozilmoqda…", 45);
            Extract(zipPath, "SmartVoiceEditor/", target);

            // 2. Python 3.12 into `runtime` (python.org's own NuGet package: a plain archive, nothing registered).
            string python = Path.Combine(target, "runtime", "python.exe");
            if (!File.Exists(python))
            {
                Report("Python 3.12 yuklanmoqda…", 50);
                string package = Path.Combine(temp, "python.3.12.10.nupkg");
                if (!File.Exists(package) || FileSha(package) != PythonSha) Download(PythonUrl, package, 50, 60);
                if (FileSha(package) != PythonSha) throw new Exception("Python paketi buzilgan (SHA256 mos emas).");
                Extract(package, "tools/", Path.Combine(target, "runtime"));
            }

            // 3. Python packages (start-backend.ps1 pins the tested versions and remembers what it installed).
            Report("Kutubxonalar o'rnatilmoqda (bir necha daqiqa)…", 62);
            if (Execute("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -File \"" + Path.Combine(target, "start-backend.ps1") + "\" -InstallOnly", target, null) != 0)
                throw new Exception("Python kutubxonalari o'rnatilmadi (log oynasiga qarang).");
            if (HasNvidia())
            {
                Report("NVIDIA videokarta topildi: CUDA kutubxonalari o'rnatilmoqda (~1.7 GB)…", 72);
                if (Execute(python, "-s -m pip install -r requirements-gpu.txt", target, null) != 0)
                    Log("CUDA kutubxonalari o'rnatilmadi — dastur protsessorda ishlaydi.");
            }

            // 4. Models chosen now (the others come with the first analysis in that language).
            if (uz || ru)
            {
                Report("Modellar yuklanmoqda…", 80);
                string which = (uz ? "uz " : "") + (ru ? "ru" : "");
                if (Execute(python, "-s tools\\fetch_models.py " + which.Trim(), target, null) != 0)
                    Log("Model yuklanmadi — birinchi tahlilda qayta urinadi.");
            }

            // 5. The panel in Premiere.
            Report("Panel Premiere Pro'ga ulanmoqda…", 95);
            if (Execute("powershell.exe", "-NoProfile -ExecutionPolicy Bypass -File \"" + Path.Combine(target, "install-panel.ps1") + "\"", target, null) != 0)
                throw new Exception("Panel Premiere'ga ulanmadi (log oynasiga qarang).");
            try { Directory.Delete(temp, true); } catch (Exception) { }
            Done(true, "O'rnatish tugadi (versiya " + version + ").\r\nPremiere Pro'ni oching: Window → Extensions → Smart Voice Editor.\r\nPapka: " + target);
        }

        // Without a window: SmartVoiceEditor-Online-Setup.exe /silent "<folder>" [uz] [ru]
        // Progress goes to <folder>.install.log; the exit code is 0 on success.
        static string silentLog;

        [STAThread]
        static int Main(string[] args)
        {
            if (args.Length >= 2 && args[0].Equals("/silent", StringComparison.OrdinalIgnoreCase))
            {
                string target = Path.GetFullPath(args[1]);
                silentLog = target.TrimEnd('\\') + ".install.log";
                bool uz = Array.IndexOf(args, "uz") > 1, ru = Array.IndexOf(args, "ru") > 1;
                OnlineSetupForm form = new OnlineSetupForm();
                try { form.Run(target, uz, ru); return form.finished ? 0 : 1; }
                catch (Exception e) { form.Log("XATO: " + e.Message); return 1; }
            }
            Application.EnableVisualStyles();
            Application.Run(new OnlineSetupForm());
            return 0;
        }
    }
}
