import { Component } from "react";

/** Shows a way out instead of a blank page when a screen crashes or a page file fails to load. */
export class ErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="mx-auto flex max-w-[640px] flex-col gap-3 p-8" role="alert">
        <h1 className="m-0 font-marker text-marker">This page didn&apos;t load</h1>
        <p className="m-0 text-body text-muted">
          Nothing you already saved was lost. Reload to try again.
        </p>
        <button
          type="button"
          className="btn btn-primary w-fit"
          onClick={() => window.location.reload()}
        >
          Reload
        </button>
      </div>
    );
  }
}
