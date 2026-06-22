import Link from "next/link";
import { useRouter } from "next/router";
import type { ReactNode } from "react";
import {
  SignInButton,
  SignedIn,
  SignedOut,
  SignOutButton,
  UserButton,
} from "@clerk/nextjs";
import { API_URL, HAS_CLERK } from "../lib/config";
import { clerkAppearance } from "../lib/clerk-appearance";

interface LayoutProps {
  children: ReactNode;
}

const NAV = [
  { href: "/", label: "Home" },
  { href: "/discover", label: "Discover" },
  { href: "/dashboard", label: "Analyze" },
];

export default function Layout({ children }: LayoutProps) {
  const router = useRouter();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-inner">
          <Link href="/" className="brand">
            <span className="brand-mark" aria-hidden>
              α
            </span>
            <span className="brand-text">
              Alpha<span>Lens</span>
            </span>
          </Link>
          <div className="app-header-right">
            <nav className="app-nav">
              {NAV.map(({ href, label }) => (
                <Link
                  key={href}
                  href={href}
                  className={router.pathname === href ? "nav-link active" : "nav-link"}
                >
                  {label}
                </Link>
              ))}
            </nav>
            {HAS_CLERK && (
              <div className="app-header-auth">
                <SignedOut>
                  <SignInButton mode="modal">
                    <button type="button" className="btn btn-header">
                      Sign in
                    </button>
                  </SignInButton>
                </SignedOut>
                <SignedIn>
                  <UserButton
                    afterSignOutUrl="/"
                    appearance={clerkAppearance}
                    userProfileMode="modal"
                  />
                  <SignOutButton redirectUrl="/">
                    <button type="button" className="btn btn-header">
                      Sign out
                    </button>
                  </SignOutButton>
                </SignedIn>
              </div>
            )}
          </div>
        </div>
      </header>
      <main className="app-main">{children}</main>
      <footer className="app-footer">
        <p className="api-hint">API · {API_URL}</p>
      </footer>
    </div>
  );
}
