import { useContext } from 'react';
import { AppContext } from './contextInstance';
import type { AppContextType } from './AppContext.types';

export function useAppContext(): AppContextType {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
}
