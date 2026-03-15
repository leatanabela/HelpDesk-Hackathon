import { supabaseAdmin } from '../config/supabase';

export interface AuthUser {
  id: string;
  email: string;
  fullName: string;
  roleId: string;
  roleName: string;
  departmentId: string | null;
}

// Verify a Supabase JWT and return the user profile
export async function verifyToken(token: string): Promise<AuthUser | null> {
  const {
    data: { user },
    error,
  } = await supabaseAdmin.auth.getUser(token);

  if (error || !user) return null;

  const { data: profile } = await supabaseAdmin
    .from('profiles')
    .select('*, roles(name)')
    .eq('id', user.id)
    .single();

  if (!profile) return null;

  return {
    id: profile.id,
    email: profile.email,
    fullName: profile.full_name,
    roleId: profile.role_id,
    roleName: profile.roles.name,
    departmentId: profile.department_id,
  };
}

// Check if a user has admin role
export async function requireAdmin(userId: string): Promise<boolean> {
  const { data } = await supabaseAdmin
    .from('profiles')
    .select('roles(name)')
    .eq('id', userId)
    .single();

  return data?.roles?.name === 'admin';
}
 