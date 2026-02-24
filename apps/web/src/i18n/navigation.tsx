import {
  Link as RRLink,
  useNavigate,
  useParams,
  useLocation,
  type LinkProps as RRLinkProps,
} from "react-router-dom";
import { useCallback } from "react";
import i18n from "./index";

type LinkProps = Omit<RRLinkProps, "to"> & { href: string };

export function Link({ href, ...props }: LinkProps) {
  const { locale } = useParams<{ locale: string }>();
  const prefix = locale ? `/${locale}` : `/${i18n.language}`;
  const to = href.startsWith("/") ? `${prefix}${href}` : href;
  return <RRLink {...props} to={to} />;
}

export function useRouter() {
  const navigate = useNavigate();
  const { locale } = useParams<{ locale: string }>();
  const prefix = locale ? `/${locale}` : `/${i18n.language}`;

  const push = useCallback(
    (path: string) => navigate(`${prefix}${path}`),
    [navigate, prefix],
  );

  const replace = useCallback(
    (path: string, opts?: { locale?: string }) => {
      const loc = opts?.locale ?? locale ?? i18n.language;
      navigate(`/${loc}${path}`, { replace: true });
    },
    [navigate, locale],
  );

  return { push, replace };
}

export function usePathname() {
  const { pathname } = useLocation();
  const { locale } = useParams<{ locale: string }>();
  if (locale && pathname.startsWith(`/${locale}`)) {
    return pathname.slice(`/${locale}`.length) || "/";
  }
  return pathname;
}
