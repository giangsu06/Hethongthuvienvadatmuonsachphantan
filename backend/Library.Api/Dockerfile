FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY backend/Library.Core/Library.Core.csproj backend/Library.Core/
COPY backend/Library.Api/Library.Api.csproj backend/Library.Api/
RUN dotnet restore backend/Library.Api/Library.Api.csproj
COPY backend/Library.Core/ backend/Library.Core/
COPY backend/Library.Api/ backend/Library.Api/
RUN dotnet publish backend/Library.Api/Library.Api.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/aspnet:10.0
WORKDIR /app
COPY --from=build /app/publish .
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080
ENTRYPOINT ["dotnet", "Library.Api.dll"]