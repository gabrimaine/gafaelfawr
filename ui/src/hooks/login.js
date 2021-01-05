import { useState, useEffect } from 'react';
import useFetch from './fetch';

export default function useLogin(setError) {
  const { data } = useFetch('/login', setError);
  const [csrf, setCsrf] = useState();
  const [username, setUsername] = useState();
  const [userScopes, setUserScopes] = useState([]);
  const [config, setConfig] = useState({ scopes: [] });

  useEffect(() => {
    if (!data) return;
    setCsrf(data.csrf);
    setUsername(data.username);
    setUserScopes(data.scopes);
    setConfig(data.config);
  }, [data]);

  return { csrf, username, userScopes, config };
}
