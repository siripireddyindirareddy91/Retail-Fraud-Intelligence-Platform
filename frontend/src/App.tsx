import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { ShieldCheck, PanelLeftClose, PanelLeftOpen, Search, Bell, Sun, Moon, ChevronRight, ChevronDown, X, Menu, Settings, ArrowUpRight, CheckCircle2, Command } from 'lucide-react';
import { catalog, groups } from './catalog';
import * as Pages from './pages';
import * as Modules from './modules';
import { api, checkHealth, errorMessage } from './services/api';
import { useAuth } from './context/AuthContext';
import { AuthScreen } from './pages/AuthScreen';
import * as Foundation from './pages/Foundation';

const modules=[Modules.SyntheticGenerator,Modules.GenerativeModels,Modules.DatasetExplorer,Modules.DataQuality,Modules.DataValidation,Modules.FraudDetection,Modules.FraudSimulator,Modules.TransactionMonitoring,Modules.FraudPatterns,Modules.RiskAnalysis,Modules.ModelTraining,Modules.ModelComparison,Modules.ModelRegistry,Modules.ModelPrediction,Modules.RobustnessTesting,Modules.DataDrift,Modules.ClassImbalance,Modules.NoiseSensitivity,Modules.UnseenFraud,Modules.PerformanceEvaluation,Modules.ShapAnalysis,Modules.FeatureImportance,Modules.PredictionExplanation,Modules.Experiments,Modules.ExperimentHistory,Modules.Reports,Modules.UserManagement];
export function App(){
 const auth=useAuth();
 const themeInteracted=useRef(false);
 const location=useLocation(),navigate=useNavigate();
 const page=catalog.find(p=>p[1]===location.pathname);
 const [collapsed,setCollapsed]=useState(()=>localStorage.getItem('sidebar-collapsed')==='true');
 const [smallScreen,setSmallScreen]=useState(()=>window.matchMedia?.('(max-width: 700px)').matches??false);
 const [mobile,setMobile]=useState(false),[theme,setThemeState]=useState(()=>localStorage.getItem('theme')||'light');
 const [searchOpen,setSearchOpen]=useState(false),[query,setQuery]=useState(''),[panel,setPanel]=useState<'notifications'|'profile'|null>(null);
 const [toast,setToast]=useState(''),[status,setStatus]=useState('Checking');
 const [resourceMatches,setResourceMatches]=useState<{id:string;name:string;type:string}[]>([]);
 useEffect(()=>{if(!auth.user||!query.trim()){setResourceMatches([]);return;}let active=true;const timer=setTimeout(()=>{api.get('/search',{params:{q:query}}).then(r=>{if(active)setResourceMatches(r.data.items)}).catch(()=>{if(active)setResourceMatches([])})},250);return()=>{active=false;clearTimeout(timer)}},[query,auth.user?.id]);
 useEffect(()=>{themeInteracted.current=false;if(auth.user)api.get('/settings').then(({data})=>{if(!themeInteracted.current){setThemeState(data.theme);localStorage.setItem('theme',data.theme)}}).catch(()=>{})},[auth.user?.id]);
 const searchRef=useRef<HTMLInputElement>(null); const searchTrigger=useRef<HTMLButtonElement>(null); const mobileToggle=useRef<HTMLButtonElement>(null);
 const notify=(message:string)=>setToast(message);
 const setTheme=(value:string)=>{themeInteracted.current=true;setThemeState(value);localStorage.setItem('theme',value)};
 useEffect(()=>{const media=window.matchMedia?.('(max-width: 700px)');if(!media)return;const update=()=>setSmallScreen(media.matches);media.addEventListener('change',update);return()=>media.removeEventListener('change',update)},[]);
 const refresh=()=>{setStatus('Checking');checkHealth().then(health=>setStatus(health.status==='research_unavailable'?'Research unavailable':'Connected')).catch(()=>setStatus('Unavailable'))};
 useEffect(()=>{document.documentElement.dataset.theme=theme},[theme]);
 useEffect(()=>{refresh();const interval=setInterval(refresh,30000);return()=>clearInterval(interval)},[]);
 useEffect(()=>{setMobile(false);setPanel(null);document.title=`${page?.[0]||'Page not found'} · Retail Fraud Intelligence`;window.scrollTo?.(0,0)},[location.pathname]);
 useEffect(()=>{if(toast){const t=setTimeout(()=>setToast(''),6000);return()=>clearTimeout(t)}},[toast]);
 useEffect(()=>{if(searchOpen)searchRef.current?.focus()},[searchOpen]);
 useEffect(()=>{const key=(e:KeyboardEvent)=>{if((e.ctrlKey||e.metaKey)&&e.key==='k'){e.preventDefault();setSearchOpen(v=>!v)}if(e.key==='Escape'){setSearchOpen(false);setPanel(null);setMobile(false);searchTrigger.current?.focus()}};document.addEventListener('keydown',key);return()=>document.removeEventListener('keydown',key)},[]);
 const searchResults=catalog.filter(p=>`${p[0]} ${groups[p[2]]}`.toLowerCase().includes(query.toLowerCase()));
 if(auth.loading||!auth.user)return <AuthScreen/>;
 return <div className={`app ${collapsed?'collapsed':''}`}><a className="skip-link" href="#main">Skip to content</a>
 {mobile&&<button className="drawer-overlay" aria-label="Close navigation" onClick={()=>setMobile(false)}/>}
 <aside inert={smallScreen&&!mobile} className={`sidebar ${mobile?'open':''}`} aria-label="Main navigation"><Link to="/dashboard" className="brand"><span className="brand-mark"><ShieldCheck size={24}/></span><span className="brand-name">Retail Fraud<span>INTELLIGENCE PLATFORM</span></span></Link><button className="mobile-close icon-button" aria-label="Close navigation" onClick={()=>{setMobile(false);mobileToggle.current?.focus()}}><X size={19}/></button>
 <div className="workspace-chip"><span className="workspace-avatar">R</span><span>Research workspace<small>{import.meta.env.PROD?'Production build':'Local environment'}</small></span><ChevronDown size={14}/></div>
 <nav>{groups.map((group,index)=><div className="nav-group" key={group}><h2>{group}</h2>{catalog.filter(p=>p[2]===index).map(([name,url,,Icon])=><NavLink onClick={()=>setMobile(false)} end title={name} aria-label={name} key={url} to={url} className={({isActive})=>isActive?'nav-item active':'nav-item'}><Icon size={17}/><span>{name}</span>{url==='/fraud/monitoring'&&<i className="nav-dot"/>}</NavLink>)}</div>)}</nav>
 <div className="sidebar-footer"><div className="research-mode"><ShieldCheck size={17}/><span>Synthetic research only<small>Built for responsible experimentation</small></span></div><button aria-label={collapsed?'Expand sidebar':'Collapse sidebar'} className="collapse-control" onClick={()=>setCollapsed(v=>{localStorage.setItem('sidebar-collapsed',String(!v));return !v})}>{collapsed?<PanelLeftOpen size={18}/>:<><PanelLeftClose size={18}/><span>Collapse sidebar</span></>}</button></div></aside>
 <div className="workspace"><header className="topbar"><button ref={mobileToggle} className="icon-button mobile-menu" aria-label="Open navigation" aria-expanded={mobile} onClick={()=>setMobile(true)}><Menu size={20}/></button><div className="breadcrumbs"><Link to="/overview">Workspace</Link><ChevronRight size={13}/><span>{page?.[0]||'Not found'}</span></div><div className="top-actions"><button ref={searchTrigger} className="search-trigger" aria-label="Search workspace" onClick={()=>setSearchOpen(true)}><Search size={16}/><span>Search workspace...</span><kbd>⌘ K</kbd></button><span className={`connection ${status==='Connected'?'online':''}`} title={`Backend: ${status}`}><i/>{status==='Connected'?'Backend connected':status==='Checking'?'Connecting':status==='Research unavailable'?'Research worker offline':'Backend offline'}</span><button className="icon-button" aria-label={`Switch to ${theme==='light'?'dark':'light'} theme`} onClick={()=>setTheme(theme==='light'?'dark':'light')}>{theme==='light'?<Moon size={18}/>:<Sun size={18}/>}</button><div className="popover-anchor"><button className="icon-button" aria-label="Notifications" aria-expanded={panel==='notifications'} onClick={()=>setPanel(panel==='notifications'?null:'notifications')}><Bell size={19}/></button>{panel==='notifications'&&<div className="popover"><h3>Notifications</h3><Foundation.BackendNotifications/></div>}</div><span className="top-divider"/><div className="popover-anchor"><button className="profile" aria-label="Workspace profile" aria-expanded={panel==='profile'} onClick={()=>setPanel(panel==='profile'?null:'profile')}>{auth.user.display_name.slice(0,1).toUpperCase()}</button>{panel==='profile'&&<div className="popover"><h3>{auth.user.display_name}</h3><p>{auth.user.email}</p><small>{auth.user.role}</small><Link to="/settings"><Settings size={15}/> Workspace settings</Link><button className="button secondary" style={{marginTop:16}} onClick={()=>auth.logout().catch(error=>notify(error.message))}>Sign out</button></div>}</div></div></header>
 <main id="main" className="main"><Routes><Route path="/" element={<Navigate to="/dashboard" replace/>}/><Route path="/dashboard" element={<Pages.Dashboard/>}/><Route path="/overview" element={<Pages.PlatformOverview/>}/>{catalog.slice(2,29).map((p,index)=>{const Component=modules[index];return <Route key={p[1]} path={p[1]} element={<Component key={p[1]} page={p} notify={notify}/>}/>})}<Route path="/settings" element={<Foundation.BackendSettings theme={theme} setTheme={setTheme} notify={notify}/>}/><Route path="/system/api" element={<Foundation.BackendApiDocs/>}/><Route path="/system/health" element={<Foundation.BackendHealth/>}/><Route path="*" element={<div className="not-found"><h1>Page not found</h1><p>This address is not part of your workspace.</p><Link className="button primary" to="/dashboard">Return to dashboard</Link></div>}/></Routes></main></div>
 {searchOpen&&<div className="modal-backdrop" onClick={()=>{setSearchOpen(false);searchTrigger.current?.focus()}}><div className="search-modal" role="dialog" aria-modal="true" aria-label="Search workspace" onClick={e=>e.stopPropagation()} onKeyDown={e=>{if(e.key==='Tab'){const focusable=e.currentTarget.querySelectorAll<HTMLElement>('input,button');const first=focusable[0],last=focusable[focusable.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}}}><div className="search-input"><Search size={21}/><input ref={searchRef} value={query} placeholder="Find a page or research module..." aria-label="Search pages" onChange={e=>setQuery(e.target.value)}/><button className="icon-button" aria-label="Close search" onClick={()=>{setSearchOpen(false);searchTrigger.current?.focus()}}><X size={18}/></button></div><div className="search-results"><span className="eyebrow">PAGES & MODULES · {searchResults.length}</span>{searchResults.map(([name,url,group,Icon])=><button key={url} onClick={()=>{navigate(url);setSearchOpen(false);setQuery('')}}><Icon size={18}/><span>{name}<small>{groups[group]}</small></span><ArrowUpRight size={15}/></button>)}{resourceMatches.map(item=><button key={item.id} onClick={()=>{navigate(item.type==="experiment"?"/experiments":item.type==="dataset"?"/datasets":item.type==="transaction"?"/fraud/monitoring?transaction="+encodeURIComponent(item.name):"/models/registry");setSearchOpen(false);setQuery('')}}><Search size={18}/><span>{item.name}<small>{item.type} · {item.id}</small></span></button>)}{searchResults.length===0&&resourceMatches.length===0&&<p>No matching pages. Try “dataset” or “model”.</p>}</div><div className="search-footer"><Command size={13}/> Search pages, datasets, models, experiments and saved transactions.</div></div></div>}
 {toast&&<div role="status" className="toast"><CheckCircle2 size={20}/><span>{toast}</span><button className="icon-button" aria-label="Dismiss notification" onClick={()=>setToast('')}><X size={16}/></button></div>}
 </div>
}








