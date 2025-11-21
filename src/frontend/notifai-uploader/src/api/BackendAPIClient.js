import { useEffect, useMemo} from 'react';
import axios from 'axios';
import { useAuth } from '../components/AuthContext.js';

export function useBackendAPIClient() {
  const { user, refreshSession } = useAuth();

  const backendAPIClient = useMemo(() => {
    const backendURL =
      window.env?.REACT_APP_BACKEND_API_BASE_URL ||
      process.env.REACT_APP_BACKEND_API_BASE_URL;
    const baseURL = backendURL?.startsWith("http")
      ? backendURL
      : `http://${backendURL}`;

    const instance = axios.create({
      baseURL: baseURL,
    });

    let isRefreshing = false;
    let failedQueue = [];
    const processQueue = (error, token = null) => {
      failedQueue.forEach((prom) => {
        if (token) {
          prom.resolve(token);
        } else {
          prom.reject(error);
        }
      });
      failedQueue = [];
    };

    instance.interceptors.response.use(
      (response) => response,
      async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
          if (isRefreshing) {
            return new Promise((resolve, reject) => {
              failedQueue.push({ resolve, reject });
            })
              .then((token) => {
                originalRequest.headers.Authorization = `Bearer ${token}`;
                return instance(originalRequest);
              })
              .catch((err) => Promise.reject(err));
          }

          originalRequest._retry = true;
          isRefreshing = true;

          try {
            const newAccessToken = await refreshSession();
            processQueue(null, newAccessToken);
            originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;
            return instance(originalRequest);
          } catch (refreshError) {
            console.error('Token refresh failed:', refreshError);
            processQueue(refreshError, null);
            sessionStorage.removeItem('accessToken');
            sessionStorage.removeItem('idToken');
            sessionStorage.removeItem('refreshToken');
            sessionStorage.removeItem('userEmail');
            window.location.href = '/login';
            return Promise.reject(refreshError);
          } finally {
            isRefreshing = false;
          }
        }

        return Promise.reject(error);
      }
    );

    return instance;
  }, [refreshSession]);

  useEffect(() => {
      const requestInterceptor = backendAPIClient.interceptors.request.use(
        (config) => {
          if (user?.accessToken) {
            config.headers.Authorization = `Bearer ${user.accessToken}`;
          }
          return config;
        },
        (error) => Promise.reject(error)
    );
    return () => {
      backendAPIClient.interceptors.request.eject(requestInterceptor);
    };
  }, [user, backendAPIClient]);
  return backendAPIClient;
}
