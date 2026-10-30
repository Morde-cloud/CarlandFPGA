"""Windows job ownership: suspended launch prevents unowned descendants."""
import ctypes
from ctypes import wintypes as w


class WindowsJob:
    def __init__(self):
        k=self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        signatures={
            'CreateJobObjectW':([w.LPVOID,w.LPCWSTR],w.HANDLE),
            'SetInformationJobObject':([w.HANDLE,ctypes.c_int,w.LPVOID,w.DWORD],w.BOOL),
            'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),
            'CloseHandle':([w.HANDLE],w.BOOL),
            'CreateToolhelp32Snapshot':([w.DWORD,w.DWORD],w.HANDLE),
            'Thread32First':([w.HANDLE,w.LPVOID],w.BOOL),
            'Thread32Next':([w.HANDLE,w.LPVOID],w.BOOL),
            'OpenThread':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),
            'ResumeThread':([w.HANDLE],w.DWORD),
        }
        for name,(args,result) in signatures.items():
            function=getattr(k,name)
            function.argtypes=args
            function.restype=result
        class Basic(ctypes.Structure):
            _fields_=[('process_time',ctypes.c_longlong),('job_time',ctypes.c_longlong),
                ('flags',w.DWORD),('min_working_set',ctypes.c_size_t),('max_working_set',ctypes.c_size_t),
                ('active_processes',w.DWORD),('affinity',ctypes.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
        class Extended(ctypes.Structure):
            _fields_=[('basic',Basic),('io',ctypes.c_ulonglong*6),
                ('process_memory',ctypes.c_size_t),('job_memory',ctypes.c_size_t),
                ('peak_process_memory',ctypes.c_size_t),('peak_job_memory',ctypes.c_size_t)]
        limits=Extended()
        limits.basic.flags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        self.handle=k.CreateJobObjectW(None,None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if not k.SetInformationJobObject(self.handle,9,ctypes.byref(limits),ctypes.sizeof(limits)):
            error=ctypes.get_last_error()
            self.close()
            raise ctypes.WinError(error)

    def attach_and_resume(self,process):
        k=self.kernel
        if not k.AssignProcessToJobObject(self.handle,int(process._handle)):
            raise ctypes.WinError(ctypes.get_last_error())
        class ThreadEntry(ctypes.Structure):
            _fields_=[('size',w.DWORD),('usage',w.DWORD),('thread_id',w.DWORD),('process_id',w.DWORD),
                ('base_priority',w.LONG),('delta_priority',w.LONG),('flags',w.DWORD)]
        snapshot=k.CreateToolhelp32Snapshot(4,0)  # TH32CS_SNAPTHREAD
        if snapshot==ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            entry=ThreadEntry()
            entry.size=ctypes.sizeof(entry)
            present=k.Thread32First(snapshot,ctypes.byref(entry))
            while present:
                if entry.process_id==process.pid:
                    thread=k.OpenThread(2,False,entry.thread_id)
                    if not thread:
                        raise ctypes.WinError(ctypes.get_last_error())
                    try:
                        if k.ResumeThread(thread)==0xffffffff:
                            raise ctypes.WinError(ctypes.get_last_error())
                    finally:
                        k.CloseHandle(thread)
                    return
                present=k.Thread32Next(snapshot,ctypes.byref(entry))
            raise RuntimeError('suspended worker primary thread was not found')
        finally:
            k.CloseHandle(snapshot)

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle=None
