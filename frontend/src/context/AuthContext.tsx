import { createContext, useContext, useEffect, useState } from 'react';
import { api, csrfToken, errorMessage, onSessionLost, refreshSession, setAccessToken, type SessionResponse, type User } from '../services/api';

type Auth={user:User|null;loading:boolean;login:(email:string,password:string)=>Promise<void>;register:(email:string,password:string,name:string)=>Promise<void>;logout:()=>Promise<void>;updateUser:(user:User)=>void};
const Context=createContext<Auth|null>(null);
export function AuthProvider({children}:{children:React.ReactNode}){
 const [user,setUser]=useState<User|null>(null),[loading,setLoading]=useState(true);
 useEffect(()=>{let active=true;const release=onSessionLost(()=>setUser(null));if(csrfToken())refreshSession().then(data=>{if(active)setUser(data.user)}).catch(()=>{}).finally(()=>{if(active)setLoading(false)});else setLoading(false);return()=>{active=false;release()}},[]);
 const accept=(data:SessionResponse)=>{setAccessToken(data.access_token);setUser(data.user)};
 const login=async(email:string,password:string)=>accept((await api.post<SessionResponse>('/auth/login',{email,password})).data);
 const register=async(email:string,password:string,name:string)=>accept((await api.post<SessionResponse>('/auth/register',{email,password,display_name:name})).data);
 const logout=async()=>{try{await api.post('/auth/logout',{}, {headers:{'X-CSRF-Token':csrfToken()}})}catch(error){throw new Error(errorMessage(error))}setAccessToken(null);setUser(null)};
 return <Context.Provider value={{user,loading,login,register,logout,updateUser:setUser}}>{children}</Context.Provider>
}
export function useAuth(){const value=useContext(Context);if(!value)throw new Error('AuthProvider is required');return value;}
