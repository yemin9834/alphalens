interface ErrorBannerProps {
  message: string;
  onDismiss?: () => void;
}

export default function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="banner banner-error" role="alert">
      <span>{message}</span>
      {onDismiss && (
        <button type="button" className="banner-dismiss" onClick={onDismiss}>
          ×
        </button>
      )}
    </div>
  );
}
