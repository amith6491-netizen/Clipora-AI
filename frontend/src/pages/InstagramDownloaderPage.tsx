import { InstagramDownloaderPanel } from "../components/video/InstagramDownloaderPanel";

export function InstagramDownloaderPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Instagram Reel & Video Studio</h1>
        <p className="mt-1 text-sm text-slate-400">
          Paste any Instagram Reel or video link to load it in high quality first, edit trim, captions, and aspect ratio in Studio, or download the HD MP4.
        </p>
      </div>

      <InstagramDownloaderPanel />
    </div>
  );
}
