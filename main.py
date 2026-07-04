from contextlib import asynccontextmanager
from datetime import date
from urllib import request

from fastapi import FastAPI, Request
import asyncpg

@asynccontextmanager
async def lifespan(app: FastAPI):
    # это выполнится ПРИ СТАРТЕ
    app.state.db = await asyncpg.connect(
        host="localhost",
        port=5432,
        database="workout_tracker",
        user="karinahanova",
        password=""
    )
    yield
    # это выполнится ПРИ ОСТАНОВКЕ
    await app.state.db.close()


app = FastAPI(lifespan=lifespan)
@app.get('/api/users')
async def get_users(request: Request):
    rows = await request.app.state.db.fetch("SELECT * FROM users")
    return [dict(row) for row in rows]

@app.get('/api/calendar')
async def get_user_workouts(month: date,
                        user_id: int):

    rows = await app.state.db.fetch('''select s.workout_date, wt.name from schedule s
                                        join workout_type wt 
                                        on s.workout_type_id = wt.id
                                        where user_id = $1 
                                            and date_trunc('month', workout_date ) = date_trunc('month', $2::date)''',
                                    user_id, month)
    return [dict(row) for row in rows]

@app.get('/api/progress')
async def get_progress(month: date,
                       user_id: int):

    rows = await app.state.db.fetch('''
                                        select 
                                                    coalesce(max(mg.goal), 0) as goal, 
                                                    count(s.workout_date) as completed, 
                                                    round((count(s.workout_date)/max(mg.goal*1.0))*100) as percent
                                        from schedule s
                                        left join month_goal mg 
                                        on s.user_id = mg.user_id 
                                            and to_char(s.workout_date, 'YYYY-MM') = to_char(mg.month, 'YYYY-MM')
                                        where s.user_id = $1 
                                            and date_trunc('month', s.workout_date)  = date_trunc('month', $2::date)
                                        group by s.user_id ''',
                                    user_id,  month)
    return [dict(row) for row in rows]

@app.get('/api/statistics')
async def get_statistics(month: date,
                            user_id: int):
    rows = await app.state.db.fetch('''
                                        select 
                                            wt.name , count(s.workout_date ) as workout_count
                                        from schedule s
                                        left join workout_type wt 
                                        on s.workout_type_id  = wt.id 
                                        where s.user_id = $1 
                                            and date_trunc('month', s.workout_date)  =  date_trunc('month', $2::date)
                                        group by wt.name
                                    ''',
                                    user_id, month)
    return [dict(row) for row in rows]