import type { AppProps } from "next/app";
import { ClerkProvider } from "@clerk/nextjs";
import { DM_Sans } from "next/font/google";
import { clerkAppearance } from "../lib/clerk-appearance";
import { HAS_CLERK } from "../lib/config";
import "../styles/globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export default function App({ Component, pageProps }: AppProps) {
  const pk = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  if (HAS_CLERK && pk) {
    return (
      <ClerkProvider
        publishableKey={pk}
        appearance={clerkAppearance}
        {...pageProps}
      >
        <div className={dmSans.className}>
          <Component {...pageProps} />
        </div>
      </ClerkProvider>
    );
  }

  return (
    <div className={dmSans.className}>
      <Component {...pageProps} />
    </div>
  );
}
