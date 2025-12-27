type CardProps = {
  children: React.ReactNode;
  className?: string;
};

export function Card({ children, className = "" }: CardProps) {
  return <div className={`glass-panel ${className}`}>{children}</div>;
}
