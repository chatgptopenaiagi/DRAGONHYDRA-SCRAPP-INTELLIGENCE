from living.launcher import main
if __name__=='__main__':
    import sys
    try:main()
    except Exception as error:
        # Windowed service invocations must fail promptly, not block on a crash dialog.
        if '--serve' in sys.argv or '--stop' in sys.argv:
            if sys.stderr:print(type(error).__name__+': '+str(error),file=sys.stderr)
            sys.exit(1)
        raise
