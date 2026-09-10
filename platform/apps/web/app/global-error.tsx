"use client";

export default function GlobalError({ reset }: { error: Error; reset: () => void }) {
  return (
    <html lang="en">
      <body>
        <main style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: "1rem", background: "#0b0f10", color: "#e8efec" }}>
          <h1>Something went wrong</h1>
          <button onClick={() => reset()} style={{ padding: "0.5rem 1rem", borderRadius: "0.5rem", background: "#14966f", color: "#0b0f10" }}>
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
