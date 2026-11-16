// A zip archive kept in several part files (<name>.001, .002, ...) so that each part fits a FAT32 flash
// drive (4 GB) and a GitHub release asset (2 GB). C# 5: compiled by the csc.exe that ships with Windows.
using System;
using System.Collections.Generic;
using System.IO;

namespace SmartVoice
{
    // Write-only, forward-only: a new part starts whenever the current one is full.
    public sealed class PartWriter : Stream
    {
        readonly string baseName;
        readonly long partSize;
        FileStream current;
        long inPart, total;
        int index;

        public PartWriter(string baseName, long partSize) { this.baseName = baseName; this.partSize = partSize; Next(); }

        public static string PartName(string baseName, int index) { return baseName + "." + index.ToString("000"); }

        void Next()
        {
            if (current != null) current.Dispose();
            index++;
            current = new FileStream(PartName(baseName, index), FileMode.Create, FileAccess.Write, FileShare.None, 1 << 20);
            inPart = 0;
        }

        public int Parts { get { return index; } }
        public override bool CanRead { get { return false; } }
        public override bool CanSeek { get { return false; } }
        public override bool CanWrite { get { return true; } }
        public override long Length { get { return total; } }
        public override long Position { get { return total; } set { throw new NotSupportedException(); } }
        public override void Flush() { current.Flush(); }
        public override int Read(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }
        public override long Seek(long offset, SeekOrigin origin) { throw new NotSupportedException(); }
        public override void SetLength(long value) { throw new NotSupportedException(); }

        public override void Write(byte[] buffer, int offset, int count)
        {
            while (count > 0)
            {
                if (inPart == partSize) Next();
                int n = (int)Math.Min(count, partSize - inPart);
                current.Write(buffer, offset, n);
                offset += n; count -= n; inPart += n; total += n;
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing && current != null) { current.Dispose(); current = null; }
            base.Dispose(disposing);
        }
    }

    // Read-only and seekable over all parts, as ZipArchive needs.
    public sealed class PartReader : Stream
    {
        readonly List<FileStream> parts = new List<FileStream>();
        readonly List<long> starts = new List<long>();
        long length, position;

        public PartReader(string baseName)
        {
            for (int i = 1; File.Exists(PartWriter.PartName(baseName, i)); i++)
            {
                FileStream s = new FileStream(PartWriter.PartName(baseName, i), FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 20);
                starts.Add(length); parts.Add(s); length += s.Length;
            }
            if (parts.Count == 0) throw new FileNotFoundException("O'rnatish fayllari topilmadi: " + PartWriter.PartName(baseName, 1));
        }

        public int Count { get { return parts.Count; } }
        public override bool CanRead { get { return true; } }
        public override bool CanSeek { get { return true; } }
        public override bool CanWrite { get { return false; } }
        public override long Length { get { return length; } }
        public override long Position { get { return position; } set { position = value; } }
        public override void Flush() { }
        public override void SetLength(long value) { throw new NotSupportedException(); }
        public override void Write(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }

        public override long Seek(long offset, SeekOrigin origin)
        {
            if (origin == SeekOrigin.Begin) position = offset;
            else if (origin == SeekOrigin.Current) position += offset;
            else position = length + offset;
            return position;
        }

        public override int Read(byte[] buffer, int offset, int count)
        {
            int done = 0;
            while (count > 0 && position < length)
            {
                int k = parts.Count - 1;
                while (starts[k] > position) k--;
                FileStream s = parts[k];
                s.Position = position - starts[k];
                int n = s.Read(buffer, offset, (int)Math.Min(count, s.Length - s.Position));
                if (n <= 0) break;
                done += n; offset += n; count -= n; position += n;
            }
            return done;
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing) foreach (FileStream s in parts) s.Dispose();
            base.Dispose(disposing);
        }
    }
}
