import {
  SignInButton,
  SignUpButton,
  SignedIn,
  SignedOut,
} from "@clerk/nextjs";
import Head from "next/head";
import Link from "next/link";
import { useEffect, useState } from "react";
import Layout from "../components/Layout";
import { checkApiHealth } from "../lib/api";
import { API_URL, HAS_CLERK } from "../lib/config";

export default function Home() {
  const [apiOk, setApiOk] = useState<boolean | null>(null);

  useEffect(() => {
    checkApiHealth().then(setApiOk);
  }, []);

  return (
    <Layout>
      <Head>
        <title>AlphaLens — Portfolio intelligence platform</title>
      </Head>

      <section className="hero-section">
        <p className="page-eyebrow">Portfolio intelligence</p>
        <h1 className="hero-title">
          Discover, analyze, and optimize.{" "}
          <span className="gradient">All in one place.</span>
        </h1>
        <p className="hero-subtitle">
          Ecosystem-based decision support for forward-thinking investors —
          map supplier networks, rank opportunities, and get portfolio-aware
          recommendations.
        </p>
        <div className="hero-cta">
          {HAS_CLERK ? (
            <>
              <SignedIn>
                <Link href="/discover" className="btn btn-primary">
                  Start discovering
                </Link>
                <Link href="/dashboard" className="btn">
                  Analyze portfolio
                </Link>
              </SignedIn>
              <SignedOut>
                <SignUpButton mode="modal">
                  <button type="button" className="btn btn-primary">
                    Get started
                  </button>
                </SignUpButton>
                <SignInButton mode="modal">
                  <button type="button" className="btn">
                    Sign in
                  </button>
                </SignInButton>
              </SignedOut>
            </>
          ) : (
            <>
              <Link href="/discover" className="btn btn-primary">
                Start discovering
              </Link>
              <Link href="/dashboard" className="btn">
                Analyze portfolio
              </Link>
            </>
          )}
        </div>
      </section>

      {apiOk === false && (
        <div className="banner banner-warn">
          Backend not reachable at {API_URL}.
          {API_URL.startsWith("http://localhost") ? (
            <>
              {" "}
              Start the API with{" "}
              <code>cd backend/api && MOCK_LAMBDAS=true uv run main.py</code>
            </>
          ) : (
            <>
              {" "}
              Check the browser console for CORS errors, confirm{" "}
              <code>NEXT_PUBLIC_API_URL</code> in <code>.env.local</code>, and
              restart <code>npm run dev</code> after env changes.
            </>
          )}
        </div>
      )}
      {apiOk === true && (
        <div className="banner banner-info">API connected — ready to analyze.</div>
      )}

      <div className="trust-row">
        <div className="trust-stat">
          <strong>5 agents</strong>
          <span>Multi-agent pipeline</span>
        </div>
        <div className="trust-stat">
          <strong>Ecosystem</strong>
          <span>Supplier & partner mapping</span>
        </div>
        <div className="trust-stat">
          <strong>Portfolio-aware</strong>
          <span>Ranked recommendations</span>
        </div>
        <div className="trust-stat">
          <strong>Production</strong>
          <span>AWS serverless stack</span>
        </div>
      </div>

      <div className="hero-grid">
        <article className="hero-card">
          <span className="hero-card-step">1</span>
          <h2>Discover</h2>
          <p className="muted">
            Find ecosystem candidates around a core company — suppliers, partners,
            and adjacent plays (e.g. NVIDIA ecosystem).
          </p>
          {HAS_CLERK ? (
            <>
              <SignedIn>
                <Link href="/discover" className="btn btn-primary">
                  Stock pool discovery
                </Link>
              </SignedIn>
              <SignedOut>
                <SignInButton mode="modal">
                  <button type="button" className="btn btn-primary">
                    Sign in to discover
                  </button>
                </SignInButton>
              </SignedOut>
            </>
          ) : (
            <Link href="/discover" className="btn btn-primary">
              Stock pool discovery
            </Link>
          )}
        </article>
        <article className="hero-card">
          <span className="hero-card-step">2</span>
          <h2>Analyze</h2>
          <p className="muted">
            Rank candidates against your holdings and receive portfolio-aware
            buy, watch, and trim recommendations.
          </p>
          {HAS_CLERK ? (
            <>
              <SignedIn>
                <Link href="/dashboard" className="btn btn-primary">
                  Portfolio analysis
                </Link>
              </SignedIn>
              <SignedOut>
                <SignInButton mode="modal">
                  <button type="button" className="btn btn-primary">
                    Sign in to analyze
                  </button>
                </SignInButton>
              </SignedOut>
            </>
          ) : (
            <Link href="/dashboard" className="btn btn-primary">
              Portfolio analysis
            </Link>
          )}
        </article>
        <article className="hero-card">
          <span className="hero-card-step">3</span>
          <h2>Async jobs</h2>
          <p className="muted">
            Run the full pipeline via SQS when Aurora and deployed agents are
            available.
          </p>
          <Link href="/dashboard" className="btn">
            From Analyze page
          </Link>
        </article>
      </div>
    </Layout>
  );
}
