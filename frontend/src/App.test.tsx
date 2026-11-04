import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { App } from './App';
import { catalog } from './catalog';
import { api } from './services/api';
vi.mock('./services/api',()=>({checkHealth:()=>Promise.reject(new Error('Offline')),api:{get:()=>Promise.reject(new Error('Offline')),post:vi.fn(()=>Promise.reject(new Error('Offline')))},errorMessage:()=> 'Backend unavailable'}));
vi.mock('./context/AuthContext',()=>({useAuth:()=>({user:{id:'test',display_name:'Researcher',email:'test@example.com',role:'researcher'},loading:false,logout:vi.fn(),updateUser:vi.fn()})}));
beforeEach(()=>localStorage.clear());
afterEach(()=>cleanup());
describe('workspace navigation',()=>{
 for(const [name,url] of catalog){it(`renders direct route ${url}`,()=>{render(<MemoryRouter initialEntries={[url]}><App/></MemoryRouter>);expect(screen.getByRole('heading',{level:1,name:url==='/dashboard'?/Intelligence starts/:name})).toBeInTheDocument();expect(screen.getByRole('navigation').querySelector('a[aria-current="page"]')).toHaveAttribute('href',url)})}
 it('search finds modules and navigates',async()=>{const user=userEvent.setup();render(<MemoryRouter><App/></MemoryRouter>);await user.click(screen.getByRole('button',{name:/Search workspace/}));const dialog=screen.getByRole('dialog');await user.type(within(dialog).getByRole('textbox'),'noise');await user.click(within(dialog).getByRole('button',{name:/Noise Sensitivity/}));expect(screen.getByRole('heading',{level:1,name:'Noise Sensitivity Testing'})).toBeInTheDocument();expect(screen.queryByRole('dialog')).not.toBeInTheDocument()});
 it('persists theme choice',async()=>{const user=userEvent.setup();render(<MemoryRouter><App/></MemoryRouter>);await user.click(screen.getByRole('button',{name:'Switch to dark theme'}));expect(document.documentElement).toHaveAttribute('data-theme','dark');expect(localStorage.getItem('theme')).toBe('dark')});
 it('retains configuration, submits the advertised API request and surfaces failure',async()=>{const user=userEvent.setup();render(<MemoryRouter initialEntries={['/synthetic/generate']}><App/></MemoryRouter>);await user.type(screen.getByLabelText('Dataset name'),'Baseline study');expect(localStorage.getItem('research:test:/synthetic/generate')).toContain('Baseline study');await user.click(screen.getByRole('button',{name:'Generate dataset'}));expect(api.post).toHaveBeenCalledWith('/datasets/generate',expect.objectContaining({name:'Baseline study',rows:10000,method:'statistical'}));expect(screen.getByRole('status')).toHaveTextContent('Backend unavailable')});
 it('handles unknown routes',()=>{render(<MemoryRouter initialEntries={['/unknown']}><App/></MemoryRouter>);expect(screen.getByRole('heading',{name:'Page not found'})).toBeInTheDocument()});
});
