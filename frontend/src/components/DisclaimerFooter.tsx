/**
 * Persistent disclaimer footer shown at the bottom of the map canvas.
 * Minimal, semi-transparent, non-intrusive.
 */
export default function DisclaimerFooter() {
  return (
    <div className="disclaimer-footer">
      <span>
        OSINT research tool — not a substitute for professional analysis.
        Data may be incomplete or delayed. AI outputs may contain errors.
        See{" "}
        <a
          href="https://github.com/chrislyonsKY/echelon/blob/main/DISCLAIMER.md"
          target="_blank"
          rel="noopener noreferrer"
        >
          full disclaimer
        </a>
        .
      </span>
    </div>
  );
}
