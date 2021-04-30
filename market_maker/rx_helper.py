import rx


def pipe_wrap(fn):
    def fn_top():
        def _fn_top(source):
            def subscribe(observer, scheduler = None):
                def on_next(value):
                    observer.on_next(fn(value))
                return source.subscribe(
                    on_next,
                    observer.on_error,
                    observer.on_completed,
                    scheduler)
            return rx.create(subscribe)
        return _fn_top
    return fn_top