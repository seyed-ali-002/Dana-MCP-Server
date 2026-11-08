/** OpenWhip assets (local first, CDN fallback). */

export const WHIP_CDN = "https://raw.githubusercontent.com/GitFrog1111/OpenWhip/main";
export const WHIP_SOUND_FILES = ["A.mp3", "B.mp3", "C.mp3", "D.mp3", "E.mp3"] as const;

/** Prefer a small local cursor; browsers ignore cursors larger than ~128×128. */
export const WHIP_CURSOR =
  'url("/whip/cursor.png") 2 2, url("/whip/divider.png") 8 8, crosshair';

const VOLUME_KEY = "dana.whip.volume";
const MUTE_KEY = "dana.whip.muted";

export function getWhipVolume(): number {
  try {
    const raw = localStorage.getItem(VOLUME_KEY);
    if (raw == null) return 0.85;
    const n = Number(raw);
    if (Number.isFinite(n)) return Math.min(1, Math.max(0, n));
  } catch {
    /* ignore */
  }
  return 0.85;
}

export function setWhipVolume(v: number): void {
  const n = Math.min(1, Math.max(0, v));
  try {
    localStorage.setItem(VOLUME_KEY, String(n));
  } catch {
    /* ignore */
  }
}

export function isWhipMuted(): boolean {
  try {
    return localStorage.getItem(MUTE_KEY) === "1";
  } catch {
    return false;
  }
}

export function setWhipMuted(muted: boolean): void {
  try {
    localStorage.setItem(MUTE_KEY, muted ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function playOpenWhipCrack(fallback?: () => void): void {
  if (isWhipMuted()) return;
  const vol = getWhipVolume();
  if (vol <= 0.001) return;
  try {
    const name = WHIP_SOUND_FILES[Math.floor(Math.random() * WHIP_SOUND_FILES.length)];
    const local = "/whip/sounds/" + name;
    const remote = WHIP_CDN + "/sounds/" + name;
    const audio = new Audio(local);
    audio.volume = vol;
    const playRemote = () => {
      try {
        const a = new Audio(remote);
        a.volume = vol;
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
