import threading
import time

def server():
    print("Servidor: Creando tuberia interna (Named Pipe)...")
    try:
        import win32pipe, win32file
        pipe = win32pipe.CreateNamedPipe(
            r'\\.\pipe\TestPipeTX3',
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536,
            0,
            None)
        print("Servidor: Tuberia creada. Esperando conexion...")
        win32pipe.ConnectNamedPipe(pipe, None)
        print("Servidor: Conexion recibida exitosamente!")
        win32file.CloseHandle(pipe)
    except ImportError:
        print("Servidor: pywin32 no instalado.")
    except Exception as e:
        print(f"Servidor Error: {e}")

def client():
    time.sleep(2)
    print("Cliente: Intentando conectar a la tuberia...")
    try:
        import win32file
        handle = win32file.CreateFile(
            r'\\.\pipe\TestPipeTX3',
            win32file.GENERIC_READ | win32file.GENERIC_WRITE,
            0,
            None,
            win32file.OPEN_EXISTING,
            0,
            None
        )
        print("Cliente: Conectado exitosamente!")
        win32file.CloseHandle(handle)
    except ImportError:
        print("Cliente: pywin32 no instalado.")
    except Exception as e:
        print(f"Cliente Error (Bloqueo Detectado): {e}")

if __name__ == "__main__":
    print("=== PRUEBA DE NUCLEO WINDOWS (NAMED PIPES) ===")
    t = threading.Thread(target=server)
    t.start()
    client()
    t.join()
    print("=== FIN DE PRUEBA ===")
