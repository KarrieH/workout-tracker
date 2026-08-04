from contextlib import asynccontextmanager
from datetime import date, datetime
from dotenv import load_dotenv
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import asyncpg
from pydantic import BaseModel

class WorkoutCreate(BaseModel):
    user_id: int
    workout_date: date
    workout_type_id: int

load_dotenv()
database = os.getenv('DB_NAME')
user = os.getenv('DB_USER')
password = os.getenv('DB_PASSWORD')
host = os.getenv('DB_HOST')



@asynccontextmanager
async def lifespan(app: FastAPI):
    # это выполнится ПРИ СТАРТЕ
    app.state.db = await asyncpg.connect(
        host=host,
        port=5432,
        database=database,
        user=user,
        password=password
    )
    yield
    # это выполнится ПРИ ОСТАНОВКЕ
    await app.state.db.close()



app = FastAPI(lifespan=lifespan)

@app.exception_handler(asyncpg.exceptions.PostgresError)
async def postgres_error_handler(request: Request, exc: asyncpg.exceptions.PostgresError):
    return JSONResponse(
        status_code=500,
        content=
        {
            "error": type(exc).__name__,  # имя класса ошибки, например "UniqueViolationError"
            "message": f"Сервис временно недоступен. Пожалуйста, попробуйте позже."
        },
    )

@app.get('/api/users')
async def get_users():
    rows = await app.state.db.fetch("SELECT * FROM users")
    return [dict(row) for row in rows]


@app.get('/api/users/by-telegram/{telegram_id}')
async def get_user_by_telegram(telegram_id: int):
    row = await app.state.db.fetchrow('''SELECT id, name FROM users
                                                where telegram_id = $1''', telegram_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)

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

@app.get('/api/workout-types')
async def get_workout_types():
    rows = await app.state.db.fetch('''select id, name
                                        from workout_type wt ''')

    return [dict(row) for row in rows]

@app.post ('/api/workouts')
async def create_workout(workout: WorkoutCreate):
    await app.state.db.fetch(
        '''
        insert into schedule (user_id, workout_date, registration_date, workout_type_id)
        values ($1, $2,NOW(), $3)
        ''',
        workout.user_id,
        workout.workout_date,
        workout.workout_type_id
    )
    return {
        "status": "success"
    }

@app.get('/api/check_workout_date')
async def get_today_workouts(workout_date: date,
                             user_id: int):
    rows = await app.state.db.fetch('''
                                        select *
                                        from schedule s 
                                        where s.user_id  = $1 and s.workout_date = $2
                                    ''',
                                    user_id, workout_date)

    return [dict(row) for row in rows]
