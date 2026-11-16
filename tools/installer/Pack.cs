// pack.exe <folder> <output base name> <part size in bytes>
// Zips <folder> (its own name becomes the top folder in the archive) into <base>.001, .002, ...
using System;
using System.IO;
using System.IO.Compression;

namespace SmartVoice
{
    static class Pack
    {
        static int Main(string[] args)
        {
            try
            {
                string folder = Path.GetFullPath(args[0]).TrimEnd('\\');
                string top = Path.GetFileName(folder);
                long size = long.Parse(args[2]);
                string[] files = Directory.GetFiles(folder, "*", SearchOption.AllDirectories);
                long sum = 0;
                foreach (string f in files) sum += new FileInfo(f).Length;
                long done = 0; int shown = -1;
                byte[] buffer = new byte[1 << 20];
                using (PartWriter output = new PartWriter(args[1], size))
                {
                    using (ZipArchive zip = new ZipArchive(output, ZipArchiveMode.Create, true))
                    {
                        foreach (string f in files)
                        {
                            FileInfo info = new FileInfo(f);
                            string name = top + "/" + f.Substring(folder.Length + 1).Replace('\\', '/');
                            // Model weights and CUDA libraries hardly compress: storing them saves a lot of time.
                            string ext = info.Extension.ToLowerInvariant();
                            CompressionLevel level = info.Length > (64 << 20) || ext == ".bin" ? CompressionLevel.NoCompression : CompressionLevel.Fastest;
                            ZipArchiveEntry entry = zip.CreateEntry(name, level);
                            entry.LastWriteTime = info.LastWriteTime;
                            using (Stream target = entry.Open())
                            using (FileStream source = info.OpenRead())
                            {
                                int n;
                                while ((n = source.Read(buffer, 0, buffer.Length)) > 0)
                                {
                                    target.Write(buffer, 0, n);
                                    done += n;
                                    int percent = (int)(done * 100 / Math.Max(1, sum));
                                    if (percent != shown) { shown = percent; Console.Write("\r" + percent + "% "); }
                                }
                            }
                        }
                    }
                    Console.WriteLine();
                    Console.WriteLine(files.Length + " files, " + output.Parts + " parts, " + (output.Length >> 20) + " MB");
                }
                return 0;
            }
            catch (Exception e) { Console.Error.WriteLine(e.ToString()); return 1; }
        }
    }
}
