import axios from 'axios';
export const api = axios.create({baseURL:'/api/v1',timeout:10000,withCredentials:true});
let accessToken: string | null = null;
let sessionLost: (()=>void) | undefined;
export function setAccessToken(value:string|null){accessToken=value;if(value)api.defaults.headers.common.Authorization=`Bearer ${value}`;else delete api.defaults.headers.common.Authorization;}
export function getAccessToken(){return accessToken;}
export function onSessionLost(callback:()=>void){sessionLost=callback;return()=>{sessionLost=undefined};}
export function csrfToken(){return document.cookie.split('; ').find(item=>item.startsWith('rf_csrf='))?.slice('rf_csrf='.length)||'';}
let refreshing:Promise<SessionResponse>|null=null;
export type User={id:string;email:string;display_name:string;role:'researcher'|'administrator';active:boolean};
export type SessionResponse={access_token:string;token_type:string;user:User};
export function refreshSession(){
 if(!refreshing)refreshing=api.post<SessionResponse>('/auth/refresh',{}, {headers:{'X-CSRF-Token':csrfToken()}}).then(({data})=>{setAccessToken(data.access_token);return data}).catch(error=>{setAccessToken(null);sessionLost?.();throw error}).finally(()=>{refreshing=null});
 return refreshing;
}
api.interceptors.response.use(response=>response,async error=>{
 const config=error.config;
 if(error.response?.status===401&&config&&!config.url?.startsWith('/auth/')&&!config._retried){config._retried=true;try{await refreshSession();config.headers.Authorization=`Bearer ${accessToken}`;return api.request(config)}catch{sessionLost?.();}}
 return Promise.reject(error);
});
export function errorMessage(error:unknown){if(!axios.isAxiosError(error))return 'The request could not be completed.';const failure=error.response?.data?.error;const detail=Array.isArray(failure?.details)?failure.details.slice(0,2).map((item:{location?:string[];message?:string})=>`${item.location?.join('.')}: ${item.message}`).join('; '):'';return `${failure?.message||'Unable to reach the backend. Check the API connection.'}${detail?` ${detail}`:''}`;}
export async function checkHealth(signal?:AbortSignal) {
  const response = await api.get('/health/ready', {
    signal,
    validateStatus: status => status === 200 || status === 503,
  });
  if (response.status === 503 && ['worker_unavailable', 'research_service_unavailable', 'storage_unavailable', 'research_service_configuration'].includes(response.data?.reason)) {
    return { status: 'research_unavailable' };
  }
  if(response.data?.status!=='ok' && response.data?.status!=='ready') throw new Error('Backend readiness has not been confirmed.');
  return response.data;
}
