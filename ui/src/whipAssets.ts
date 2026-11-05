/** OpenWhip assets (local first, CDN fallback). */
export const WHIP_CDN = "https://raw.githubusercontent.com/GitFrog1111/OpenWhip/main";
export const WHIP_SOUND_FILES = ["A.mp3", "B.mp3", "C.mp3", "D.mp3", "E.mp3"] as const;

export const WHIP_CURSOR =
  'url("/whip/divider.png") 8 8, url("' +
  WHIP_CDN +
  '/assets/divider.png") 8 8, crosshair';

export function playOpenWhipCrack(fallback?: () => void): void {
  try {
    const name = WHIP_SOUND_FILES[Math.floor(Math.random() * WHIP_SOUND_FILES.length)];
    const local = "/whip/sounds/" + name;
    const remote = WHIP_CDN + "/sounds/" + name;
    const audio = new Audio(local);
    audio.volume = 0.9;
    const playRemote = () => {
      try {
        const a = new Audio(remote);
        a.volume = 0.9;
        void a.play().catch(() => fallback?.());
      } catch {
        fallback?.();
      }
    };
    audio.addEventListener("error", playRemote);
    void audio.play().catch(playRemote);
  } catch {
    fallback?.();
  }
}
